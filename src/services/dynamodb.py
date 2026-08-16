import os

import boto3


# ---------------------------------------------------------
# AWS region
# ---------------------------------------------------------

AWS_REGION = os.getenv(
    "AWS_REGION",
    os.getenv(
        "AWS_DEFAULT_REGION",
        "eu-west-1",
    ),
)


# ---------------------------------------------------------
# DynamoDB resource
# ---------------------------------------------------------

dynamodb = boto3.resource(
    "dynamodb",
    region_name=AWS_REGION,
)


# ---------------------------------------------------------
# Table names
#
# Lambda/SAM supplies these through environment variables.
#
# Local development falls back to the SentinelIQ
# table names.
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

print(
    "DYNAMODB CONFIG:",
    {
        "region": AWS_REGION,
        "transactions": TRANSACTIONS_TABLE_NAME,
        "fraud_results": FRAUD_RESULTS_TABLE_NAME,
        "customer_profiles": CUSTOMER_PROFILES_TABLE_NAME,
    }
)