import os

import boto3
from dotenv import load_dotenv

from src.lambda_function.sync_handler import lambda_handler


load_dotenv()

REGION = os.getenv("AWS_REGION", "eu-west-1")
TABLE_NAME = "FraudResults"

dynamodb = boto3.client(
    "dynamodb",
    region_name=REGION,
)


def main():

    print("Reading one real FraudResults record...")

    response = dynamodb.scan(
        TableName=TABLE_NAME,
        Limit=1,
    )

    items = response.get("Items", [])

    if not items:
        raise RuntimeError(
            "No records found in FraudResults"
        )

    item = items[0]

    transaction_reference = item[
        "transaction_reference"
    ]["S"]

    print(
        f"Testing transaction: "
        f"{transaction_reference}"
    )

    event = {
        "Records": [
            {
                "eventID": "test-event-001",
                "eventName": "INSERT",
                "eventVersion": "1.1",
                "eventSource": "aws:dynamodb",
                "awsRegion": REGION,
                "dynamodb": {
                    "Keys": {
                        "transaction_reference": {
                            "S": transaction_reference
                        }
                    },
                    "NewImage": item,
                },
                "eventSourceARN": (
                    "arn:aws:dynamodb:"
                    f"{REGION}:"
                    "table/FraudResults/stream/test"
                ),
            }
        ]
    }

    result = lambda_handler(event, None)

    print()
    print("Lambda result:")
    print(result)


if __name__ == "__main__":
    main()