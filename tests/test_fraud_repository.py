from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from src.models.fraud_result import FraudResult
from src.repositories.fraud_repository import FraudRepository


def make_fraud_result():
    return FraudResult(
        transaction_reference="TX-REPO-001",
        risk_score=82,
        risk_level="HIGH",
        is_fraud=True,
        reasons="New device detected",
        evaluated_at=datetime(
            2026,
            8,
            27,
            12,
            0,
            0,
            tzinfo=UTC,
        ),
    )


def make_decision():
    return {
        "decision": "DECLINE",
        "decision_reason": "High fraud risk",
        "risk_score": 82,
        "risk_level": "HIGH",
        "is_fraud": True,
        "velocity_violation": False,
    }


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_get_result_returns_none_when_result_does_not_exist(
    mock_table,
):
    mock_table.get_item.return_value = {}

    repository = FraudRepository()

    result = repository.get_result("TX-MISSING")

    assert result is None

    mock_table.get_item.assert_called_once_with(
        Key={
            "transaction_reference": "TX-MISSING",
        }
    )


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_get_result_reconstructs_fraud_result_and_decision(
    mock_table,
):
    mock_table.get_item.return_value = {
        "Item": {
            "transaction_reference": "TX-REPO-001",
            "risk_score": 82,
            "risk_level": "HIGH",
            "is_fraud": True,
            "reasons": "New device detected",
            "evaluated_at": (
                "2026-08-27T12:00:00+00:00"
            ),
            "decision": "DECLINE",
            "decision_reason": "High fraud risk",
            "decision_risk_score": 82,
            "decision_risk_level": "HIGH",
            "decision_is_fraud": True,
            "velocity_violation": False,
        }
    }

    repository = FraudRepository()

    result = repository.get_result("TX-REPO-001")

    assert result is not None
    assert result["fraud_result"].transaction_reference == (
        "TX-REPO-001"
    )
    assert result["fraud_result"].risk_score == 82
    assert result["fraud_result"].risk_level == "HIGH"
    assert result["fraud_result"].is_fraud is True
    assert result["fraud_result"].reasons == (
        "New device detected"
    )
    assert result["fraud_result"].evaluated_at == datetime(
        2026,
        8,
        27,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    assert result["decision"] == {
        "decision": "DECLINE",
        "decision_reason": "High fraud risk",
        "risk_score": 82,
        "risk_level": "HIGH",
        "is_fraud": True,
        "velocity_violation": False,
    }


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_get_result_supports_legacy_fraud_result(
    mock_table,
):
    mock_table.get_item.return_value = {
        "Item": {
            "transaction_reference": "TX-LEGACY-001",
            "risk_score": 82,
            "risk_level": "HIGH",
            "is_fraud": True,
            "reasons": "Suspicious activity",
            "evaluated_at": (
                "2026-08-27T12:00:00+00:00"
            ),
        }
    }

    repository = FraudRepository()

    result = repository.get_result("TX-LEGACY-001")

    assert result is not None
    assert result["fraud_result"].risk_score == 82
    assert result["decision"]["decision"] == "DECLINE"
    assert result["decision"]["velocity_violation"] is False


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_insert_result_if_absent_stores_decision_snapshot(
    mock_table,
):
    repository = FraudRepository()

    result = make_fraud_result()
    decision = make_decision()

    stored = repository.insert_result_if_absent(
        result,
        decision,
    )

    assert stored is True

    expected_item = result.to_dict()

    expected_item.update(
        {
            "decision": "DECLINE",
            "decision_reason": "High fraud risk",
            "decision_risk_score": 82,
            "decision_risk_level": "HIGH",
            "decision_is_fraud": True,
            "velocity_violation": False,
        }
    )

    mock_table.put_item.assert_called_once_with(
        Item=expected_item,
        ConditionExpression=(
            "attribute_not_exists("
            "transaction_reference"
            ")"
        ),
    )


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_insert_result_if_absent_returns_false_for_duplicate(
    mock_table,
):
    mock_table.put_item.side_effect = ClientError(
        {
            "Error": {
                "Code": (
                    "ConditionalCheckFailedException"
                ),
                "Message": "The conditional request failed",
            }
        },
        "PutItem",
    )

    repository = FraudRepository()

    stored = repository.insert_result_if_absent(
        make_fraud_result(),
        make_decision(),
    )

    assert stored is False


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_insert_result_if_absent_reraises_unexpected_client_error(
    mock_table,
):
    mock_table.put_item.side_effect = ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Throughput exceeded",
            }
        },
        "PutItem",
    )

    repository = FraudRepository()

    with pytest.raises(ClientError):
        repository.insert_result_if_absent(
            make_fraud_result(),
            make_decision(),
        )


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_insert_result_preserves_existing_behaviour(
    mock_table,
):
    repository = FraudRepository()

    result = make_fraud_result()

    repository.insert_result(result)

    mock_table.put_item.assert_called_once_with(
        Item=result.to_dict()
    )


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_count_results_returns_dynamodb_count(
    mock_table,
):
    mock_table.scan.return_value = {
        "Count": 13,
    }

    repository = FraudRepository()

    assert repository.count_results() == 13

    mock_table.scan.assert_called_once_with(
        Select="COUNT"
    )


@patch(
    "src.repositories.fraud_repository.FRAUD_RESULTS_TABLE"
)
def test_get_result_reraises_dynamodb_error(
    mock_table,
):
    mock_table.get_item.side_effect = ClientError(
        {
            "Error": {
                "Code": "InternalServerError",
                "Message": "DynamoDB error",
            }
        },
        "GetItem",
    )

    repository = FraudRepository()

    with pytest.raises(ClientError):
        repository.get_result("TX-ERROR")