import os
from datetime import datetime, timezone

import boto3
import psycopg2
from dotenv import load_dotenv


load_dotenv()


AWS_REGION = os.getenv("AWS_REGION", "eu-west-1")
DYNAMODB_TABLE = os.getenv("DYNAMODB_TABLE", "FraudResults")

PG_HOST = os.getenv("DB_HOST", "localhost")
PG_PORT = os.getenv("DB_PORT", "5432")
PG_NAME = os.getenv("DB_NAME", "fintech_fraud")
PG_USER = os.getenv("DB_USER", "postgres")
PG_PASSWORD = os.getenv("DB_PASSWORD")


def parse_timestamp(value):
    """Convert DynamoDB timestamp string to timezone-aware datetime."""
    timestamp = datetime.fromisoformat(value)

    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)

    return timestamp


def get_dynamodb_items():
    """Retrieve all fraud results from DynamoDB."""
    dynamodb = boto3.resource(
        "dynamodb",
        region_name=AWS_REGION,
    )

    table = dynamodb.Table(DYNAMODB_TABLE)

    items = []

    scan_kwargs = {}

    while True:
        response = table.scan(**scan_kwargs)
        items.extend(response.get("Items", []))

        last_key = response.get("LastEvaluatedKey")

        if not last_key:
            break

        scan_kwargs["ExclusiveStartKey"] = last_key

    return items


def sync_to_postgres(items):
    """Upsert DynamoDB fraud results into PostgreSQL."""
    connection = psycopg2.connect(
        host=PG_HOST,
        port=PG_PORT,
        dbname=PG_NAME,
        user=PG_USER,
        password=PG_PASSWORD,
    )

    try:
        with connection:
            with connection.cursor() as cursor:

                for item in items:
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
                            item["transaction_reference"],
                            int(item["risk_score"]),
                            item["risk_level"],
                            bool(item["is_fraud"]),
                            item.get("reasons"),
                            parse_timestamp(item["evaluated_at"]),
                        ),
                    )

        return len(items)

    finally:
        connection.close()


def main():
    print("Starting DynamoDB → PostgreSQL synchronization...")

    print(f"Source table: {DYNAMODB_TABLE}")
    print(f"AWS region: {AWS_REGION}")
    print(f"Target database: {PG_NAME}")

    items = get_dynamodb_items()

    print(f"DynamoDB records retrieved: {len(items)}")

    synced = sync_to_postgres(items)

    print(f"Records synchronized: {synced}")
    print("Synchronization completed successfully.")


if __name__ == "__main__":
    main()