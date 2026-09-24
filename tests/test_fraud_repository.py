from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

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


def make_repository():
    repository = FraudRepository.__new__(
        FraudRepository
    )

    repository.region_name = "eu-west-1"
    repository.table_name = "FraudResults"
    repository.dynamodb = MagicMock()
    repository.table = MagicMock()

    return repository


def conditional_failure():
    return ClientError(
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


def unexpected_dynamodb_error():
    return ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Capacity exceeded",
            }
        },
        "PutItem",
    )


def test_repository_initializes_default_configuration(
    monkeypatch,
):
    monkeypatch.delenv(
        "AWS_REGION_NAME",
        raising=False,
    )
    monkeypatch.delenv(
        "FRAUD_RESULTS_TABLE",
        raising=False,
    )

    repository = FraudRepository()

    assert repository.region_name == "eu-west-1"
    assert repository.table_name == "FraudResults"
    assert repository.table is not None


def test_repository_uses_custom_environment_configuration(
    monkeypatch,
):
    monkeypatch.setenv(
        "AWS_REGION_NAME",
        "us-east-1",
    )
    monkeypatch.setenv(
        "FRAUD_RESULTS_TABLE",
        "CustomFraudResults",
    )

    repository = FraudRepository()

    assert repository.region_name == "us-east-1"
    assert repository.table_name == (
        "CustomFraudResults"
    )


def test_result_item_serializes_domain_model():
    result = make_fraud_result()

    item = FraudRepository._result_item(
        result
    )

    assert item == {
        "transaction_reference": (
            "TX-REPO-001"
        ),
        "risk_score": 82,
        "risk_level": "HIGH",
        "is_fraud": True,
        "reasons": "New device detected",
        "evaluated_at": (
            "2026-08-27T12:00:00+00:00"
        ),
    }


def test_result_item_normalizes_naive_datetime():
    result = make_fraud_result()
    result.evaluated_at = datetime(
        2026,
        8,
        27,
        12,
        0,
        0,
    )

    item = FraudRepository._result_item(
        result
    )

    assert item["evaluated_at"] == (
        "2026-08-27T12:00:00+00:00"
    )


def test_result_with_decision_item_serializes_complete_snapshot():
    item = FraudRepository._result_with_decision_item(
        make_fraud_result(),
        make_decision(),
    )

    assert item == {
        "transaction_reference": (
            "TX-REPO-001"
        ),
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


def test_item_to_fraud_result_reconstructs_model():
    item = {
        "transaction_reference": (
            "TX-REPO-001"
        ),
        "risk_score": Decimal("82"),
        "risk_level": "HIGH",
        "is_fraud": True,
        "reasons": "New device detected",
        "evaluated_at": (
            "2026-08-27T12:00:00+00:00"
        ),
    }

    result = FraudRepository._item_to_fraud_result(
        item
    )

    assert result.transaction_reference == (
        "TX-REPO-001"
    )
    assert result.risk_score == 82
    assert result.risk_level == "HIGH"
    assert result.is_fraud is True
    assert result.reasons == (
        "New device detected"
    )
    assert result.evaluated_at == datetime(
        2026,
        8,
        27,
        12,
        0,
        0,
        tzinfo=UTC,
    )


def test_item_to_fraud_result_normalizes_naive_datetime():
    item = {
        "transaction_reference": "TX-NAIVE",
        "risk_score": Decimal("10"),
        "risk_level": "LOW",
        "is_fraud": False,
        "reasons": "Normal",
        "evaluated_at": (
            "2026-08-27T12:00:00"
        ),
    }

    result = FraudRepository._item_to_fraud_result(
        item
    )

    assert result.evaluated_at == datetime(
        2026,
        8,
        27,
        12,
        0,
        0,
        tzinfo=UTC,
    )


def test_get_result_returns_none_when_missing():
    repository = make_repository()

    repository.table.get_item.return_value = {}

    result = repository.get_result(
        "TX-MISSING"
    )

    assert result is None

    repository.table.get_item.assert_called_once_with(
        Key={
            "transaction_reference": "TX-MISSING"
        }
    )


def test_get_result_reconstructs_result_and_decision():
    repository = make_repository()

    repository.table.get_item.return_value = {
        "Item": {
            "transaction_reference": (
                "TX-REPO-001"
            ),
            "risk_score": Decimal("82"),
            "risk_level": "HIGH",
            "is_fraud": True,
            "reasons": "New device detected",
            "evaluated_at": (
                "2026-08-27T12:00:00+00:00"
            ),
            "decision": "DECLINE",
            "decision_reason": "High fraud risk",
            "decision_risk_score": Decimal("82"),
            "decision_risk_level": "HIGH",
            "decision_is_fraud": True,
            "velocity_violation": False,
        }
    }

    result = repository.get_result(
        "TX-REPO-001"
    )

    assert result is not None

    fraud_result = result["fraud_result"]

    assert fraud_result.transaction_reference == (
        "TX-REPO-001"
    )
    assert fraud_result.risk_score == 82
    assert fraud_result.risk_level == "HIGH"
    assert fraud_result.is_fraud is True
    assert fraud_result.reasons == (
        "New device detected"
    )
    assert fraud_result.evaluated_at == datetime(
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


def test_get_result_supports_legacy_fraud_result():
    repository = make_repository()

    repository.table.get_item.return_value = {
        "Item": {
            "transaction_reference": (
                "TX-LEGACY-001"
            ),
            "risk_score": Decimal("82"),
            "risk_level": "HIGH",
            "is_fraud": True,
            "reasons": "Suspicious activity",
            "evaluated_at": (
                "2026-08-27T12:00:00+00:00"
            ),
        }
    }

    result = repository.get_result(
        "TX-LEGACY-001"
    )

    assert result is not None
    assert result["fraud_result"].risk_score == 82
    assert result["decision"]["decision"] == (
        "DECLINE"
    )
    assert result["decision"]["decision_reason"] == (
        "Existing fraud result"
    )
    assert result["decision"]["risk_score"] == 82
    assert result["decision"]["risk_level"] == (
        "HIGH"
    )
    assert result["decision"]["is_fraud"] is True
    assert result["decision"]["velocity_violation"] is False


@pytest.mark.parametrize(
    ("risk_score", "is_fraud", "expected"),
    [
        (80, False, "DECLINE"),
        (40, True, "DECLINE"),
        (79, True, "DECLINE"),
        (40, False, "REVIEW"),
        (39, True, "APPROVE"),
        (39, False, "APPROVE"),
    ],
)
def test_legacy_decision_mapping(
    risk_score,
    is_fraud,
    expected,
):
    result = FraudResult(
        transaction_reference="TX-LEGACY",
        risk_score=risk_score,
        risk_level="HIGH",
        is_fraud=is_fraud,
        reasons="Legacy",
        evaluated_at=datetime.now(UTC),
    )

    assert (
        FraudRepository._legacy_decision(result)
        == expected
    )


def test_insert_result_writes_dynamodb_item():
    repository = make_repository()

    result = make_fraud_result()

    repository.insert_result(result)

    repository.table.put_item.assert_called_once_with(
        Item={
            "transaction_reference": (
                "TX-REPO-001"
            ),
            "risk_score": 82,
            "risk_level": "HIGH",
            "is_fraud": True,
            "reasons": "New device detected",
            "evaluated_at": (
                "2026-08-27T12:00:00+00:00"
            ),
        }
    )


def test_insert_result_propagates_dynamodb_error():
    repository = make_repository()

    repository.table.put_item.side_effect = (
        RuntimeError("DynamoDB unavailable")
    )

    with pytest.raises(RuntimeError):
        repository.insert_result(
            make_fraud_result()
        )


def test_insert_result_if_absent_writes_conditionally():
    repository = make_repository()

    stored = repository.insert_result_if_absent(
        make_fraud_result(),
        make_decision(),
    )

    assert stored is True

    repository.table.put_item.assert_called_once_with(
        Item={
            "transaction_reference": (
                "TX-REPO-001"
            ),
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
        },
        ConditionExpression=(
            "attribute_not_exists("
            "transaction_reference)"
        ),
    )


def test_insert_result_if_absent_returns_false_for_duplicate():
    repository = make_repository()

    repository.table.put_item.side_effect = (
        conditional_failure()
    )

    stored = repository.insert_result_if_absent(
        make_fraud_result(),
        make_decision(),
    )

    assert stored is False

    repository.table.put_item.assert_called_once()


def test_insert_result_if_absent_reraises_unexpected_client_error():
    repository = make_repository()

    repository.table.put_item.side_effect = (
        unexpected_dynamodb_error()
    )

    with pytest.raises(ClientError):
        repository.insert_result_if_absent(
            make_fraud_result(),
            make_decision(),
        )


def test_insert_result_if_absent_propagates_unexpected_error():
    repository = make_repository()

    repository.table.put_item.side_effect = (
        RuntimeError("DynamoDB unavailable")
    )

    with pytest.raises(RuntimeError):
        repository.insert_result_if_absent(
            make_fraud_result(),
            make_decision(),
        )


def test_count_results_returns_single_page_count():
    repository = make_repository()

    repository.table.scan.return_value = {
        "Count": 13
    }

    assert repository.count_results() == 13

    repository.table.scan.assert_called_once_with()


def test_count_results_paginates_all_pages():
    repository = make_repository()

    repository.table.scan.side_effect = [
        {
            "Count": 10,
            "LastEvaluatedKey": {
                "transaction_reference": "TX-010"
            },
        },
        {
            "Count": 3
        },
    ]

    assert repository.count_results() == 13

    assert repository.table.scan.call_count == 2

    repository.table.scan.assert_any_call()

    repository.table.scan.assert_any_call(
        ExclusiveStartKey={
            "transaction_reference": "TX-010"
        }
    )


def test_get_result_propagates_dynamodb_error():
    repository = make_repository()

    repository.table.get_item.side_effect = (
        RuntimeError("DynamoDB unavailable")
    )

    with pytest.raises(RuntimeError):
        repository.get_result("TX-ERROR")
