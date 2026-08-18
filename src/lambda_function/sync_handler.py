
import logging
import os
from datetime import datetime, timezone

import psycopg2


logger = logging.getLogger()
logger.setLevel(logging.INFO)


def parse_dynamodb_value(value):
    """
    Convert a DynamoDB Streams AttributeValue into a native Python value.
    """

    if "S" in value:
        return value["S"]

    if "N" in value:
        number = value["N"]

        if "." in number:
            return float(number)

        return int(number)

    if "BOOL" in value:
        return value["BOOL"]

    if "NULL" in value:
        return None

    if "M" in value:
        return {
            key: parse_dynamodb_value(item)
            for key, item in value["M"].items()
        }

    if "L" in value:
        return [
            parse_dynamodb_value(item)
            for item in value["L"]
        ]

    return None


def deserialize_image(image):
    """Convert a DynamoDB Stream image into a normal dictionary."""

    return {
        key: parse_dynamodb_value(value)
        for key, value in image.items()
    }


def get_postgres_connection():
    """Create a PostgreSQL connection from environment variables."""

    return psycopg2.connect(
        host=os.environ["DB_HOST"],
        port=os.environ.get("DB_PORT", "5432"),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
    )


def sync_record(record):
    """
    Synchronize one DynamoDB Stream record into PostgreSQL.
    """

    event_name = record.get("eventName")

    if event_name not in ("INSERT", "MODIFY"):
        logger.info(
            "Skipping event type: %s",
            event_name,
        )
        return

    dynamodb = record.get("dynamodb", {})
    new_image = dynamodb.get("NewImage")

    if not new_image:
        logger.warning("No NewImage found in stream record")
        return

    fraud_result = deserialize_image(new_image)

    transaction_reference = fraud_result.get(
        "transaction_reference"
    )

    if not transaction_reference:
        logger.warning(
            "Skipping record without transaction_reference"
        )
        return

    evaluated_at = fraud_result.get("evaluated_at")

    if isinstance(evaluated_at, str):
        evaluated_at = datetime.fromisoformat(
            evaluated_at.replace("Z", "+00:00")
        )

    connection = get_postgres_connection()

    try:
        with connection:
            with connection.cursor() as cursor:

                cursor.execute(
                    """
                    INSERT INTO fraud_results_analytics (
                        transaction_reference,
                        risk_score,
                        risk_level,
                        is_fraud,
                        reasons,
                        evaluated_at
                    )
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (transaction_reference)
                    DO UPDATE SET
                        risk_score = EXCLUDED.risk_score,
                        risk_level = EXCLUDED.risk_level,
                        is_fraud = EXCLUDED.is_fraud,
                        reasons = EXCLUDED.reasons,
                        evaluated_at = EXCLUDED.evaluated_at,
                        synced_at = CURRENT_TIMESTAMP
                    """,
                    (
                        transaction_reference,
                        int(fraud_result.get("risk_score", 0)),
                        fraud_result.get("risk_level"),
                        bool(fraud_result.get("is_fraud", False)),
                        fraud_result.get("reasons"),
                        evaluated_at,
                    ),
                )

        logger.info(
            "Synchronized fraud result: %s",
            transaction_reference,
        )

    finally:
        connection.close()


def lambda_handler(event, context):
    """Process DynamoDB Stream events."""

    records = event.get("Records", [])

    logger.info(
        "Received %d DynamoDB Stream records",
        len(records),
    )

    processed = 0

    for record in records:
        try:
            sync_record(record)
            processed += 1

        except Exception:
            logger.exception(
                "Failed to process DynamoDB Stream record"
            )
            raise

    return {
        "statusCode": 200,
        "processed": processed,
    }