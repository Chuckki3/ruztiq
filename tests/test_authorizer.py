
import json
from unittest.mock import patch

import pytest

from src.lambda_function import authorizer


@pytest.fixture
def method_arn():
    return (
        "arn:aws:execute-api:eu-west-1:619240106198:"
        "5a6400nk92/Prod/POST/score"
    )


def test_extract_bearer_token():
    event = {
        "headers": {
            "Authorization": "Bearer test-token-123"
        }
    }

    assert authorizer._extract_bearer_token(event) == "test-token-123"


def test_extract_bearer_token_case_insensitive_header():
    event = {
        "headers": {
            "authorization": "Bearer test-token-123"
        }
    }

    assert authorizer._extract_bearer_token(event) == "test-token-123"


@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "",
        "Basic test-token",
        "Bearer",
        "Bearer ",
        "test-token",
    ],
)
def test_extract_bearer_token_rejects_invalid_header(authorization):
    event = {
        "headers": {
            "Authorization": authorization
        }
    }

    assert authorizer._extract_bearer_token(event) is None


@patch(
    "src.lambda_function.authorizer._get_api_token",
    return_value="correct-token",
)
def test_authorizer_allows_valid_token(mock_get_token, method_arn):
    event = {
        "headers": {
            "Authorization": "Bearer correct-token"
        },
        "methodArn": method_arn,
    }

    result = authorizer.lambda_handler(event, None)

    assert result["principalId"] == "ruztiq-client"
    assert (
        result["policyDocument"]["Statement"][0]["Effect"]
        == "Allow"
    )
    assert (
        result["policyDocument"]["Statement"][0]["Resource"]
        == method_arn
    )

    mock_get_token.assert_called_once()


@patch(
    "src.lambda_function.authorizer._get_api_token",
    return_value="correct-token",
)
def test_authorizer_denies_invalid_token(mock_get_token, method_arn):
    event = {
        "headers": {
            "Authorization": "Bearer wrong-token"
        },
        "methodArn": method_arn,
    }

    result = authorizer.lambda_handler(event, None)

    assert result["principalId"] == "unauthorized"
    assert (
        result["policyDocument"]["Statement"][0]["Effect"]
        == "Deny"
    )
    assert (
        result["policyDocument"]["Statement"][0]["Resource"]
        == method_arn
    )

    mock_get_token.assert_called_once()


def test_authorizer_denies_missing_token(method_arn):
    event = {
        "headers": {},
        "methodArn": method_arn,
    }

    result = authorizer.lambda_handler(event, None)

    assert result["principalId"] == "anonymous"
    assert (
        result["policyDocument"]["Statement"][0]["Effect"]
        == "Deny"
    )


@patch(
    "src.lambda_function.authorizer._get_api_token",
    return_value="correct-token",
)
def test_authorizer_accepts_lowercase_bearer_scheme(
    mock_get_token,
    method_arn,
):
    event = {
        "headers": {
            "Authorization": "bearer correct-token"
        },
        "methodArn": method_arn,
    }

    result = authorizer.lambda_handler(event, None)

    assert (
        result["policyDocument"]["Statement"][0]["Effect"]
        == "Allow"
    )


@patch(
    "src.lambda_function.authorizer.secrets_manager.get_secret_value"
)
def test_get_api_token(mock_get_secret_value):
    mock_get_secret_value.return_value = {
        "SecretString": json.dumps(
            {"token": "secret-token"}
        )
    }

    assert authorizer._get_api_token() == "secret-token"

    mock_get_secret_value.assert_called_once_with(
        SecretId=authorizer.SECRET_NAME
    )


@patch(
    "src.lambda_function.authorizer.secrets_manager.get_secret_value"
)
def test_get_api_token_rejects_missing_token(
    mock_get_secret_value,
):
    mock_get_secret_value.return_value = {
        "SecretString": json.dumps({})
    }

    with pytest.raises(ValueError):
        authorizer._get_api_token()

