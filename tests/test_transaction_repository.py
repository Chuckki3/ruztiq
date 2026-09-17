from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.models.transaction import Transaction
from src.repositories.transaction_repository import (
    TransactionRepository,
)


@pytest.fixture
def repository():
    with patch(
        "src.repositories.transaction_repository.boto3.client"
    ) as mock_client:
        repo = TransactionRepository()
        repo.secrets_client = mock_client.return_value
        return repo


@pytest.fixture
def transaction():
    return Transaction(
        customer_id=1001,
        transaction_reference="txn-001",
        amount=150.75,
        merchant_name="Test Merchant",
        merchant_category="Retail",
        payment_method="Card",
        device_type="Mobile",
        transaction_time=datetime(
            2026,
            9,
            14,
            18,
            30,
            tzinfo=UTC,
        ),
        location="Lagos",
        ip_address="192.168.1.10",
        status="APPROVED",
    )


@pytest.fixture
def connection():
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = (
        MagicMock()
    )
    return connection


def configure_credentials(repository):
    repository.secrets_client.get_secret_value.return_value = {
        "SecretString": (
            '{"username":"test_user","password":"test_password"}'
        )
    }


def get_cursor(connection):
    return connection.cursor.return_value.__enter__.return_value


def test_insert_transaction_persists_transaction(
    repository,
    transaction,
    connection,
):
    configure_credentials(repository)

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.insert_transaction(transaction)

    cursor = get_cursor(connection)

    assert result == "txn-001"

    cursor.execute.assert_called_once()

    query, params = cursor.execute.call_args.args

    assert "INSERT INTO transactions" in query
    assert "transaction_reference" in query
    assert "customer_id" in query
    assert "transaction_time" in query

    assert params == (
        "txn-001",
        1001,
        Decimal("150.75"),
        "Test Merchant",
        "Retail",
        "Card",
        "Mobile",
        datetime(
            2026,
            9,
            14,
            18,
            30,
            tzinfo=UTC,
        ),
        "Lagos",
        "192.168.1.10",
        "APPROVED",
    )

    connection.commit.assert_called_once()
    connection.rollback.assert_not_called()
    connection.close.assert_called_once()


def test_insert_transaction_normalizes_naive_datetime(
    repository,
    transaction,
    connection,
):
    configure_credentials(repository)

    transaction.transaction_time = datetime(
        2026,
        9,
        14,
        18,
        30,
    )

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        repository.insert_transaction(transaction)

    cursor = get_cursor(connection)
    _, params = cursor.execute.call_args.args

    assert params[7] == datetime(
        2026,
        9,
        14,
        18,
        30,
        tzinfo=UTC,
    )


def test_insert_transaction_normalizes_non_utc_datetime(
    repository,
    transaction,
    connection,
):
    configure_credentials(repository)

    from datetime import timezone, timedelta

    transaction.transaction_time = datetime(
        2026,
        9,
        14,
        19,
        30,
        tzinfo=timezone(timedelta(hours=1)),
    )

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        repository.insert_transaction(transaction)

    cursor = get_cursor(connection)
    _, params = cursor.execute.call_args.args

    assert params[7] == datetime(
        2026,
        9,
        14,
        18,
        30,
        tzinfo=UTC,
    )


def test_insert_transaction_rolls_back_on_error(
    repository,
    transaction,
    connection,
):
    configure_credentials(repository)

    cursor = get_cursor(connection)
    cursor.execute.side_effect = RuntimeError(
        "database insert failed"
    )

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        with pytest.raises(
            RuntimeError,
            match="database insert failed",
        ):
            repository.insert_transaction(transaction)

    connection.rollback.assert_called_once()
    connection.commit.assert_not_called()
    connection.close.assert_called_once()


def test_insert_transaction_closes_connection_on_error(
    repository,
    transaction,
    connection,
):
    configure_credentials(repository)

    cursor = get_cursor(connection)
    cursor.execute.side_effect = ValueError(
        "insert failure"
    )

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        with pytest.raises(
            ValueError,
            match="insert failure",
        ):
            repository.insert_transaction(transaction)

    connection.close.assert_called_once()


def test_count_transactions_returns_count(
    repository,
    connection,
):
    configure_credentials(repository)

    cursor = get_cursor(connection)
    cursor.fetchone.return_value = (17,)

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.count_transactions()

    assert result == 17

    query = cursor.execute.call_args.args[0]

    assert "SELECT COUNT(*)" in query
    assert "FROM transactions" in query

    connection.close.assert_called_once()


def test_count_transactions_converts_count_to_integer(
    repository,
    connection,
):
    cursor = get_cursor(connection)
    cursor.fetchone.return_value = ("42",)

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.count_transactions()

    assert result == 42
    assert isinstance(result, int)


def test_get_recent_transactions_queries_velocity_window(
    repository,
    connection,
):
    cursor = get_cursor(connection)
    cursor.fetchall.return_value = []

    transaction_time = datetime(
        2026,
        9,
        14,
        18,
        30,
        tzinfo=UTC,
    )

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.get_recent_transactions(
            customer_id=1001,
            transaction_time=transaction_time,
            window_minutes=5,
        )

    assert result == []

    query, params = cursor.execute.call_args.args

    assert "FROM transactions" in query
    assert "WHERE customer_id = %s" in query
    assert (
        "transaction_time BETWEEN %s AND %s"
        in query
    )
    assert "ORDER BY transaction_time" in query

    assert params == (
        1001,
        datetime(
            2026,
            9,
            14,
            18,
            25,
            tzinfo=UTC,
        ),
        datetime(
            2026,
            9,
            14,
            18,
            30,
            tzinfo=UTC,
        ),
    )

    connection.close.assert_called_once()


def test_get_recent_transactions_normalizes_naive_query_time(
    repository,
    connection,
):
    cursor = get_cursor(connection)
    cursor.fetchall.return_value = []

    naive_time = datetime(
        2026,
        9,
        14,
        18,
        30,
    )

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        repository.get_recent_transactions(
            customer_id=1001,
            transaction_time=naive_time,
            window_minutes=5,
        )

    _, params = cursor.execute.call_args.args

    assert params[1] == datetime(
        2026,
        9,
        14,
        18,
        25,
        tzinfo=UTC,
    )

    assert params[2] == datetime(
        2026,
        9,
        14,
        18,
        30,
        tzinfo=UTC,
    )


def test_get_recent_transactions_reconstructs_transactions(
    repository,
    connection,
):
    cursor = get_cursor(connection)

    historical_time = datetime(
        2026,
        9,
        14,
        18,
        28,
        tzinfo=UTC,
    )

    cursor.fetchall.return_value = [
        (
            "txn-history-001",
            1001,
            Decimal("275.50"),
            "Supermarket",
            "Groceries",
            "Card",
            "Mobile",
            historical_time,
            "Lagos",
            "10.0.0.1",
            "APPROVED",
        )
    ]

    query_time = datetime(
        2026,
        9,
        14,
        18,
        30,
        tzinfo=UTC,
    )

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.get_recent_transactions(
            customer_id=1001,
            transaction_time=query_time,
            window_minutes=5,
        )

    assert len(result) == 1

    result_transaction = result[0]

    assert isinstance(
        result_transaction,
        Transaction,
    )
    assert (
        result_transaction.transaction_reference
        == "txn-history-001"
    )
    assert result_transaction.customer_id == 1001
    assert result_transaction.amount == 275.50
    assert (
        result_transaction.merchant_name
        == "Supermarket"
    )
    assert (
        result_transaction.merchant_category
        == "Groceries"
    )
    assert (
        result_transaction.payment_method
        == "Card"
    )
    assert (
        result_transaction.device_type
        == "Mobile"
    )
    assert (
        result_transaction.transaction_time
        == historical_time
    )
    assert result_transaction.location == "Lagos"
    assert result_transaction.ip_address == "10.0.0.1"
    assert result_transaction.status == "APPROVED"


def test_get_recent_transactions_skips_missing_timestamp(
    repository,
    connection,
):
    cursor = get_cursor(connection)

    cursor.fetchall.return_value = [
        (
            "txn-invalid",
            1001,
            Decimal("100.00"),
            "Merchant",
            "Retail",
            "Card",
            "Mobile",
            None,
            "Lagos",
            "10.0.0.1",
            "APPROVED",
        )
    ]

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.get_recent_transactions(
            customer_id=1001,
            transaction_time=datetime(
                2026,
                9,
                14,
                18,
                30,
                tzinfo=UTC,
            ),
            window_minutes=5,
        )

    assert result == []


def test_get_recent_transactions_normalizes_naive_historical_time(
    repository,
    connection,
):
    cursor = get_cursor(connection)

    cursor.fetchall.return_value = [
        (
            "txn-naive",
            1001,
            Decimal("100.00"),
            "Merchant",
            "Retail",
            "Card",
            "Mobile",
            datetime(
                2026,
                9,
                14,
                18,
                28,
            ),
            "Lagos",
            "10.0.0.1",
            "APPROVED",
        )
    ]

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.get_recent_transactions(
            customer_id=1001,
            transaction_time=datetime(
                2026,
                9,
                14,
                18,
                30,
                tzinfo=UTC,
            ),
            window_minutes=5,
        )

    assert len(result) == 1

    assert result[0].transaction_time == datetime(
        2026,
        9,
        14,
        18,
        28,
        tzinfo=UTC,
    )


def test_get_recent_transactions_skips_malformed_row(
    repository,
    connection,
):
    cursor = get_cursor(connection)

    cursor.fetchall.return_value = [
        (
            "txn-malformed",
            "not-an-integer",
            Decimal("100.00"),
            "Merchant",
            "Retail",
            "Card",
            "Mobile",
            datetime(
                2026,
                9,
                14,
                18,
                28,
                tzinfo=UTC,
            ),
            "Lagos",
            "10.0.0.1",
            "APPROVED",
        )
    ]

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.get_recent_transactions(
            customer_id=1001,
            transaction_time=datetime(
                2026,
                9,
                14,
                18,
                30,
                tzinfo=UTC,
            ),
            window_minutes=5,
        )

    assert result == []


def test_get_recent_transactions_propagates_query_error(
    repository,
    connection,
):
    cursor = get_cursor(connection)
    cursor.execute.side_effect = RuntimeError(
        "database query failed"
    )

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        with pytest.raises(
            RuntimeError,
            match="database query failed",
        ):
            repository.get_recent_transactions(
                customer_id=1001,
                transaction_time=datetime(
                    2026,
                    9,
                    14,
                    18,
                    30,
                    tzinfo=UTC,
                ),
                window_minutes=5,
            )

    connection.close.assert_called_once()


def test_get_random_customer_id_returns_customer_id(
    repository,
    connection,
):
    cursor = get_cursor(connection)
    cursor.fetchone.return_value = (1001,)

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.get_random_customer_id()

    assert result == 1001

    query = cursor.execute.call_args.args[0]

    assert "SELECT customer_id" in query
    assert "FROM transactions" in query
    assert "ORDER BY RANDOM()" in query
    assert "LIMIT 1" in query

    connection.close.assert_called_once()


def test_get_random_customer_id_falls_back_when_empty(
    repository,
    connection,
):
    cursor = get_cursor(connection)
    cursor.fetchone.return_value = None

    with patch.object(
        repository,
        "_get_connection",
        return_value=connection,
    ):
        result = repository.get_random_customer_id()

    assert result == 1
    connection.close.assert_called_once()


def test_get_connection_loads_credentials_from_secrets_manager(
    repository,
):
    repository.secrets_client.get_secret_value.return_value = {
        "SecretString": (
            '{"username":"db_user","password":"db_password"}'
        )
    }

    with patch(
        "src.repositories.transaction_repository.psycopg2.connect"
    ) as mock_connect:
        result = repository._get_connection()

    repository.secrets_client.get_secret_value.assert_called_once_with(
        SecretId=repository.secret_name
    )

    mock_connect.assert_called_once_with(
        host=repository.db_host,
        port=repository.db_port,
        dbname=repository.db_name,
        user="db_user",
        password="db_password",
        connect_timeout=10,
    )

    assert result == mock_connect.return_value
