import logging
from datetime import datetime

from src.repositories.analytics_repository import AnalyticsRepository


logger = logging.getLogger()
logger.setLevel(logging.INFO)


analytics_repository = AnalyticsRepository()


def parse_dynamodb_value(value):
    """Convert a DynamoDB Streams AttributeValue into a native Python value."""
    if "S" in value:
        return value["S"]

    if "N" in value:
        number = value["N"]
        return float(number) if "." in number else int(number)

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
    """Convert a DynamoDB Stream image into a normal Python dictionary."""
    return {
        key: parse_dynamodb_value(value)
        for key, value in image.items()
    }


def sync_record(record):
    """
    Process one DynamoDB Stream record and delegate analytics persistence
    to AnalyticsRepository.
    """
    event_name = record.get("eventName")

    if event_name not in ("INSERT", "MODIFY"):
        logger.info("Skipping event type: %s", event_name)
        return

    dynamodb = record.get("dynamodb", {})
    new_image = dynamodb.get("NewImage")

    if not new_image:
        logger.warning("No NewImage found in stream record")
        return

    fraud_result = deserialize_image(new_image)

    transaction_reference = fraud_result.get("transaction_reference")

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

    risk_score = fraud_result.get("risk_score", 0)

    try:
        risk_score = int(risk_score)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid risk_score for transaction %s. "
            "Defaulting to 0.",
            transaction_reference,
        )
        risk_score = 0

    risk_level = fraud_result.get("risk_level")
    is_fraud = fraud_result.get("is_fraud", False)
    reasons = fraud_result.get("reasons")

    if isinstance(is_fraud, str):
        is_fraud = is_fraud.lower() == "true"

    logger.info(
        "Synchronizing transaction %s | risk_score=%s | "
        "risk_level=%s | is_fraud=%s",
        transaction_reference,
        risk_score,
        risk_level,
        is_fraud,
    )

    analytics_repository.save_fraud_result(
        transaction_reference=transaction_reference,
        risk_score=risk_score,
        risk_level=risk_level,
        is_fraud=is_fraud,
        reasons=reasons,
        evaluated_at=evaluated_at,
    )


def lambda_handler(event, context):
    """
    AWS Lambda entry point.

    Processes DynamoDB Stream events and delegates PostgreSQL
    persistence to AnalyticsRepository.
    """
    records = event.get("Records", [])

    logger.info(
        "Received %d DynamoDB Stream records",
        len(records),
    )

    processed = 0
    skipped = 0

    for record in records:
        try:
            event_name = record.get("eventName")

            if event_name not in ("INSERT", "MODIFY"):
                skipped += 1
                logger.info(
                    "Skipping unsupported event type: %s",
                    event_name,
                )
                continue

            sync_record(record)
            processed += 1

        except Exception:
            logger.exception(
                "Failed to process DynamoDB Stream record"
            )
            raise

    logger.info(
        "DynamoDB Stream processing complete | "
        "processed=%d | skipped=%d | total=%d",
        processed,
        skipped,
        len(records),
    )

    return {
        "statusCode": 200,
        "processed": processed,
        "skipped": skipped,
        "total_records": len(records),
    }