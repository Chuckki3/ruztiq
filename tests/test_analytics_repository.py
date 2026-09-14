import json
from unittest.mock import MagicMock

import pytest

from src.repositories.analytics_repository import AnalyticsRepository


def test_get_postgres_connection_uses_secret_credentials():
    secrets_client = MagicMock()
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "test_user",
                "password": "test_password",
            }
        )
    }

    repository = AnalyticsRepository(
        secret_name="test/secret",
        db_host="localhost",
        db_port="5432",
        db_name="test_db",
        secrets_client=secrets_client,
    )

    connection = MagicMock()

    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setattr(
            "src.repositories.analytics_repository.psycopg2.connect",
            MagicMock(return_value=connection),
        )

        result = repository.get_postgres_connection()

    assert result is connection

    secrets_client.get_secret_value.assert_called_once_with(
        SecretId="test/secret"
    )


def test_get_postgres_connection_rejects_missing_secret_string():
    secrets_client = MagicMock()
    secrets_client.get_secret_value.return_value = {}

    repository = AnalyticsRepository(
        secret_name="test/secret",
        db_host="localhost",
        db_name="test_db",
        secrets_client=secrets_client,
    )

    with pytest.raises(
        ValueError,
        match="does not contain SecretString",
    ):
        repository.get_postgres_connection()


def test_get_postgres_connection_rejects_missing_credentials():
    secrets_client = MagicMock()
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "test_user",
            }
        )
    }

    repository = AnalyticsRepository(
        secret_name="test/secret",
        db_host="localhost",
        db_name="test_db",
        secrets_client=secrets_client,
    )

    with pytest.raises(
        ValueError,
        match="credentials missing",
    ):
        repository.get_postgres_connection()


def test_get_postgres_connection_requires_database_host(monkeypatch):
    monkeypatch.delenv("DB_HOST", raising=False)

    secrets_client = MagicMock()
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "test_user",
                "password": "test_password",
            }
        )
    }

    repository = AnalyticsRepository(
        secret_name="test/secret",
        db_name="test_db",
        secrets_client=secrets_client,
    )

    with pytest.raises(
        ValueError,
        match="DB_HOST",
    ):
        repository.get_postgres_connection()


def test_get_postgres_connection_requires_database_name(monkeypatch):
    monkeypatch.delenv("DB_NAME", raising=False)

    secrets_client = MagicMock()
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "test_user",
                "password": "test_password",
            }
        )
    }

    repository = AnalyticsRepository(
        secret_name="test/secret",
        db_host="localhost",
        secrets_client=secrets_client,
    )

    with pytest.raises(
        ValueError,
        match="DB_NAME",
    ):
        repository.get_postgres_connection()


def test_save_fraud_result_writes_expected_values():
    connection = MagicMock()
    cursor = MagicMock()

    connection.cursor.return_value.__enter__.return_value = cursor
    connection.__enter__.return_value = connection

    repository = AnalyticsRepository(
        secret_name="test/secret",
        db_host="localhost",
        db_name="test_db",
    )

    repository.get_postgres_connection = MagicMock(
        return_value=connection
    )

    repository.save_fraud_result(
        transaction_reference="TX-001",
        risk_score=45,
        risk_level="MEDIUM",
        is_fraud=False,
        reasons="Late Night",
        evaluated_at="2026-09-14T10:00:00+00:00",
    )

    repository.get_postgres_connection.assert_called_once()

    cursor.execute.assert_called_once()

    sql, values = cursor.execute.call_args.args

    assert "INSERT INTO fraud_results_analytics" in sql
    assert "ON CONFLICT (transaction_reference)" in sql

    assert values == (
        "TX-001",
        45,
        "MEDIUM",
        False,
        "Late Night",
        "2026-09-14T10:00:00+00:00",
    )

    connection.close.assert_called_once()