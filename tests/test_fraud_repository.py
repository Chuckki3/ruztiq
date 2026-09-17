from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

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
    repository = FraudRepository()
    repository._get_database_credentials = MagicMock(
        return_value=("test-user", "test-password")
    )
    return repository


def make_connection():
    connection = MagicMock()
    cursor = connection.cursor.return_value
    return connection, cursor


@patch(
    "src.repositories.fraud_repository.boto3.client"
)
def test_repository_initializes_secrets_client(
    mock_boto_client,
):
    repository = FraudRepository()

    mock_boto_client.assert_called_once_with(
        "secretsmanager"
    )
    assert repository.db_secret_name == (
        "sentineliq/rds/postgres"
    )
    assert repository.db_port == 5432


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_get_result_returns_none_when_result_does_not_exist(
    mock_connect,
):
    connection, cursor = make_connection()
    cursor.fetchone.return_value = None
    mock_connect.return_value = connection

    repository = make_repository()

    result = repository.get_result("TX-MISSING")

    assert result is None

    cursor.execute.assert_called_once()
    assert cursor.execute.call_args.args[1] == (
        "TX-MISSING",
    )
    cursor.close.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_get_result_reconstructs_fraud_result_and_decision(
    mock_connect,
):
    connection, cursor = make_connection()

    evaluated_at = datetime(
        2026,
        8,
        27,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    cursor.fetchone.return_value = (
        "TX-REPO-001",
        82,
        "HIGH",
        True,
        "New device detected",
        evaluated_at,
        "DECLINE",
        "High fraud risk",
        82,
        "HIGH",
        True,
        False,
    )

    mock_connect.return_value = connection

    repository = make_repository()

    result = repository.get_result("TX-REPO-001")

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
    assert fraud_result.evaluated_at == evaluated_at

    assert result["decision"] == {
        "decision": "DECLINE",
        "decision_reason": "High fraud risk",
        "risk_score": 82,
        "risk_level": "HIGH",
        "is_fraud": True,
        "velocity_violation": False,
    }

    cursor.close.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_get_result_supports_legacy_fraud_result(
    mock_connect,
):
    connection, cursor = make_connection()

    evaluated_at = datetime(
        2026,
        8,
        27,
        12,
        0,
        0,
        tzinfo=UTC,
    )

    cursor.fetchone.return_value = (
        "TX-LEGACY-001",
        82,
        "HIGH",
        True,
        "Suspicious activity",
        evaluated_at,
        None,
        None,
        None,
        None,
        None,
        None,
    )

    mock_connect.return_value = connection

    repository = make_repository()

    result = repository.get_result("TX-LEGACY-001")

    assert result is not None
    assert result["fraud_result"].risk_score == 82
    assert result["decision"]["decision"] == "DECLINE"
    assert result["decision"]["decision_reason"] == (
        "Existing fraud result"
    )
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


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_insert_result_persists_fraud_result(
    mock_connect,
):
    connection, cursor = make_connection()
    mock_connect.return_value = connection

    repository = make_repository()
    result = make_fraud_result()

    repository.insert_result(result)

    assert cursor.execute.call_count == 1

    query, params = cursor.execute.call_args.args

    assert "INSERT INTO fraud_results" in query
    assert "transaction_reference" in query
    assert "risk_score" in query
    assert "evaluated_at" in query

    assert params == (
        "TX-REPO-001",
        82,
        "HIGH",
        True,
        "New device detected",
        result.evaluated_at,
    )

    connection.commit.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_insert_result_rolls_back_on_error(
    mock_connect,
):
    connection, cursor = make_connection()
    cursor.execute.side_effect = RuntimeError(
        "database error"
    )
    mock_connect.return_value = connection

    repository = make_repository()

    with pytest.raises(RuntimeError):
        repository.insert_result(
            make_fraud_result()
        )

    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_insert_result_if_absent_stores_decision_snapshot(
    mock_connect,
):
    connection, cursor = make_connection()
    cursor.fetchone.return_value = (
        "TX-REPO-001",
    )
    mock_connect.return_value = connection

    repository = make_repository()

    stored = repository.insert_result_if_absent(
        make_fraud_result(),
        make_decision(),
    )

    assert stored is True

    query, params = cursor.execute.call_args.args

    assert "ON CONFLICT" in query
    assert "DO NOTHING" in query
    assert "RETURNING transaction_reference" in query

    assert params == (
        "TX-REPO-001",
        82,
        "HIGH",
        True,
        "New device detected",
        make_fraud_result().evaluated_at,
        "DECLINE",
        "High fraud risk",
        82,
        "HIGH",
        True,
        False,
    )

    connection.commit.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_insert_result_if_absent_returns_false_for_duplicate(
    mock_connect,
):
    connection, cursor = make_connection()
    cursor.fetchone.return_value = None
    mock_connect.return_value = connection

    repository = make_repository()

    stored = repository.insert_result_if_absent(
        make_fraud_result(),
        make_decision(),
    )

    assert stored is False
    connection.commit.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_insert_result_if_absent_rolls_back_on_error(
    mock_connect,
):
    connection, cursor = make_connection()
    cursor.execute.side_effect = RuntimeError(
        "database unavailable"
    )
    mock_connect.return_value = connection

    repository = make_repository()

    with pytest.raises(RuntimeError):
        repository.insert_result_if_absent(
            make_fraud_result(),
            make_decision(),
        )

    connection.rollback.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_count_results_returns_postgresql_count(
    mock_connect,
):
    connection, cursor = make_connection()
    cursor.fetchone.return_value = (13,)
    mock_connect.return_value = connection

    repository = make_repository()

    assert repository.count_results() == 13

    query = cursor.execute.call_args.args[0]

    assert "SELECT COUNT(*)" in query
    assert "FROM fraud_results" in query

    cursor.close.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_database_connection_uses_secret_credentials(
    mock_connect,
):
    connection, cursor = make_connection()
    cursor.fetchone.return_value = None
    mock_connect.return_value = connection

    repository = make_repository()

    repository.get_result("TX-CONNECTION")

    mock_connect.assert_called_once_with(
        host=repository.db_host,
        port=repository.db_port,
        dbname=repository.db_name,
        user="test-user",
        password="test-password",
        connect_timeout=10,
    )

    cursor.close.assert_called_once()
    connection.close.assert_called_once()


@patch(
    "src.repositories.fraud_repository.psycopg2.connect"
)
def test_get_result_rolls_up_connection_failure(
    mock_connect,
):
    mock_connect.side_effect = RuntimeError(
        "connection failed"
    )

    repository = make_repository()

    with pytest.raises(RuntimeError):
        repository.get_result("TX-ERROR")
