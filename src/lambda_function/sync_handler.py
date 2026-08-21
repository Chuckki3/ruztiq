import json
import logging
import os
from datetime import datetime

import boto3
import psycopg2

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# AWS Secrets Manager
# ---------------------------------------------------------------------------

SECRET_NAME = os.environ.get("DB_SECRET_NAME", "sentineliq/rds/postgres")
secrets_client = boto3.client("secretsmanager")

# ---------------------------------------------------------------------------
# DynamoDB Stream Deserialization
# ---------------------------------------------------------------------------

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
        return {key: parse_dynamodb_value(item) for key, item in value["M"].items()}
    if "L" in value:
        return [parse_dynamodb_value(item) for item in value["L"]]
    return None

def deserialize_image(image):
    """Convert a DynamoDB Stream image into a normal Python dictionary."""
    return {key: parse_dynamodb_value(value) for key, value in image.items()}

# ---------------------------------------------------------------------------
# PostgreSQL Connection
# ---------------------------------------------------------------------------

def get_postgres_connection():
    """Create a PostgreSQL connection using credentials stored in AWS Secrets Manager."""
    logger.info("Retrieving PostgreSQL credentials from Secrets Manager: %s", SECRET_NAME)

    secret_response = secrets_client.get_secret_value(SecretId=SECRET_NAME)
    secret_string = secret_response.get("SecretString")

    if not secret_string:
        raise ValueError("Secrets Manager secret does not contain SecretString")

    secret = json.loads(secret_string)
    username = secret.get("username")
    password = secret.get("password")

    if not username or not password:
        raise ValueError("PostgreSQL credentials missing from Secrets Manager secret")

    db_host = os.environ["DB_HOST"]
    db_port = os.environ.get("DB_PORT", "5432")
    db_name = os.environ["DB_NAME"]

    logger.info("Connecting to PostgreSQL database '%s' at '%s:%s'", db_name, db_host, db_port)

    return psycopg2.connect(
        host=db_host,
        port=db_port,
        dbname=db_name,
        user=username,
        password=password,
        connect_timeout=10,
    )

# ---------------------------------------------------------------------------
# Fraud Result Synchronization
# ---------------------------------------------------------------------------

def sync_record(record):
    """Synchronize one DynamoDB Stream record into PostgreSQL."""
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
        logger.warning("Skipping record without transaction_reference")
        return

    evaluated_at = fraud_result.get("evaluated_at")
    if isinstance(evaluated_at, str):
        evaluated_at = datetime.fromisoformat(evaluated_at.replace("Z", "+00:00"))

    risk_score = fraud_result.get("risk_score", 0)
    try:
        risk_score = int(risk_score)
    except (TypeError, ValueError):
        logger.warning("Invalid risk_score for transaction %s. Defaulting to 0.", transaction_reference)
        risk_score = 0

    risk_level = fraud_result.get("risk_level")
    is_fraud = fraud_result.get("is_fraud", False)
    reasons = fraud_result.get("reasons")

    if isinstance(is_fraud, str):
        is_fraud = is_fraud.lower() == "true"

    logger.info(
        "Synchronizing transaction %s | risk_score=%s | risk_level=%s | is_fraud=%s",
        transaction_reference, risk_score, risk_level, is_fraud,
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
                    (transaction_reference, risk_score, risk_level, is_fraud, reasons, evaluated_at),
                )
        logger.info("Successfully synchronized fraud result: %s", transaction_reference)
    finally:
        connection.close()

# ---------------------------------------------------------------------------
# Lambda Handler
# ---------------------------------------------------------------------------

def lambda_handler(event, context):
    """AWS Lambda entry point. Processes DynamoDB Stream events and synchronizes fraud results into PostgreSQL."""
    records = event.get("Records", [])
    logger.info("Received %d DynamoDB Stream records", len(records))

    processed = 0
    skipped = 0

    for record in records:
        try:
            event_name = record.get("eventName")
            if event_name not in ("INSERT", "MODIFY"):
                skipped += 1
                logger.info("Skipping unsupported event type: %s", event_name)
                continue

            sync_record(record)
            processed += 1

        except Exception:
            logger.exception("Failed to process DynamoDB Stream record")
            raise  # Let Lambda retry according to event source mapping

    logger.info(
        "DynamoDB Stream processing complete | processed=%d | skipped=%d | total=%d",
        processed, skipped, len(records),
    )

    return {
        "statusCode": 200,
        "processed": processed,
        "skipped": skipped,
        "total_records": len(records),
    }
