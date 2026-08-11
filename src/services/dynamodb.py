import os

import boto3


# ---------------------------------------------------------
# DynamoDB resource
# ---------------------------------------------------------

dynamodb = boto3.resource("dynamodb")


# ---------------------------------------------------------
# Table names
#
# Lambda/SAM supplies these through environment variables.
#
# Local development falls back to the actual SentinelIQ
# table names so imports and local tests do not fail simply
# because Lambda environment variables are unavailable.
# ---------------------------------------------------------

TRANSACTIONS_TABLE_NAME = os.getenv(
    "TRANSACTIONS_TABLE",
    "Transactions",
)

FRAUD_RESULTS_TABLE_NAME = os.getenv(
    "FRAUD_RESULTS_TABLE",
    "FraudResults",
)

CUSTOMER_PROFILES_TABLE_NAME = os.getenv(
    "CUSTOMER_PROFILES_TABLE",
    "CustomerProfiles",
)


# ---------------------------------------------------------
# DynamoDB table handles
# ---------------------------------------------------------

TRANSACTIONS_TABLE = dynamodb.Table(
    TRANSACTIONS_TABLE_NAME
)

FRAUD_RESULTS_TABLE = dynamodb.Table(
    FRAUD_RESULTS_TABLE_NAME
)

CUSTOMER_PROFILES_TABLE = dynamodb.Table(
    CUSTOMER_PROFILES_TABLE_NAME
)