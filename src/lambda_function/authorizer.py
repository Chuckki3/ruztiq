
import hmac
import json
import logging
import os

import boto3
from botocore.exceptions import BotoCoreError, ClientError


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

secrets_manager = boto3.client(
    "secretsmanager",
    region_name=os.environ.get("AWS_REGION", "eu-west-1"),
)

SECRET_NAME = os.environ.get(
    "API_AUTH_SECRET_NAME",
    "sentineliq/api/auth",
)


def _deny_policy(principal_id: str, method_arn: str) -> dict:
    """Return an API Gateway IAM Deny policy."""
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Deny",
                    "Resource": method_arn,
                }
            ],
        },
    }


def _allow_policy(principal_id: str, method_arn: str) -> dict:
    """Return an API Gateway IAM Allow policy."""
    return {
        "principalId": principal_id,
        "policyDocument": {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Action": "execute-api:Invoke",
                    "Effect": "Allow",
                    "Resource": method_arn,
                }
            ],
        },
    }


def _get_api_token() -> str:
    """Retrieve the expected API credential from Secrets Manager."""
    response = secrets_manager.get_secret_value(
        SecretId=SECRET_NAME
    )

    secret_string = response.get("SecretString")

    if not secret_string:
        raise ValueError("API authentication secret has no SecretString.")

    secret = json.loads(secret_string)
    token = secret.get("token")

    if not isinstance(token, str) or not token:
        raise ValueError(
            "API authentication secret does not contain a valid token."
        )

    return token


def _extract_bearer_token(event: dict) -> str | None:
    """Extract a Bearer token from the Authorization header."""
    headers = event.get("headers") or {}

    authorization = None

    for name, value in headers.items():
        if name.lower() == "authorization":
            authorization = value
            break

    if not authorization or not isinstance(authorization, str):
        return None

    parts = authorization.strip().split(None, 1)

    if len(parts) != 2:
        return None

    scheme, token = parts

    if scheme.lower() != "bearer" or not token:
        return None

    return token.strip()


def lambda_handler(event, context):
    """
    AWS Lambda REQUEST authorizer for the RuztIQ API.

    Expected request header:

        Authorization: Bearer <token>

    The token is validated against the credential stored in
    AWS Secrets Manager.
    """
    method_arn = event.get("methodArn", "*")

    supplied_token = _extract_bearer_token(event)

    if not supplied_token:
        logger.warning("Authorization header missing or malformed.")
        return _deny_policy("anonymous", method_arn)

    try:
        expected_token = _get_api_token()
    except (ClientError, BotoCoreError, ValueError, json.JSONDecodeError):
        logger.exception("Unable to retrieve API authentication credential.")
        return _deny_policy("authentication-error", method_arn)

    if not hmac.compare_digest(supplied_token, expected_token):
        logger.warning("API authentication failed.")
        return _deny_policy("unauthorized", method_arn)

    logger.info("API authentication successful.")
    return _allow_policy("ruztiq-client", method_arn)

