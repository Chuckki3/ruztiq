import os

import boto3


dynamodb = boto3.resource("dynamodb")


TRANSACTIONS_TABLE = dynamodb.Table(
    os.environ["TRANSACTIONS_TABLE"]
)

FRAUD_RESULTS_TABLE = dynamodb.Table(
    os.environ["FRAUD_RESULTS_TABLE"]
)