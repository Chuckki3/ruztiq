import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from src.models.customer_profile import CustomerProfile
from src.repositories.customer_profile_repository import (
    CustomerProfileRepository,
)


@pytest.fixture
def secrets_client():
    return MagicMock()


@pytest.fixture
def repository(secrets_client):
    return CustomerProfileRepository(
        secret_name="test/secret",
        db_host="localhost",
        db_port="5432",
        db_name="fintech_fraud",
        secrets_client=secrets_client,
    )


@pytest.fixture
def profile():
    return CustomerProfile(
        customer_id=1001,
        first_seen=datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        last_seen=datetime(2026, 9, 14, 15, 30, tzinfo=UTC),
        total_transactions=3,
        total_amount=450.75,
        average_amount=150.25,
        highest_amount=250.00,
        lowest_amount=75.75,
        failed_transactions=1,
        successful_transactions=2,
        known_devices=["mobile", "web"],
        known_locations=["Lagos", "Abuja"],
        known_payment_methods=["card", "bank_transfer"],
        known_merchants=["Merchant A", "Merchant B"],
        known_ips=["10.0.0.1", "10.0.0.2"],
        recent_transactions=[
            {
                "transaction_reference": "TXN-001",
                "amount": 100.0,
            },
            {
                "transaction_reference": "TXN-002",
                "amount": 200.0,
            },
        ],
    )


def test_get_postgres_connection_uses_secret_credentials(
    repository,
    secrets_client,
):
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "postgres_user",
                "password": "postgres_password",
            }
        )
    }

    fake_connection = MagicMock()

    with patch(
        "src.repositories.customer_profile_repository.psycopg2.connect",
        return_value=fake_connection,
    ) as connect_mock:
        result = repository.get_postgres_connection()

    assert result is fake_connection

    secrets_client.get_secret_value.assert_called_once_with(
        SecretId="test/secret"
    )

    connect_mock.assert_called_once_with(
        host="localhost",
        port="5432",
        dbname="fintech_fraud",
        user="postgres_user",
        password="postgres_password",
        connect_timeout=10,
    )


def test_get_postgres_connection_rejects_missing_secret_string(
    repository,
    secrets_client,
):
    secrets_client.get_secret_value.return_value = {}

    with pytest.raises(
        ValueError,
        match="Secrets Manager secret does not contain SecretString",
    ):
        repository.get_postgres_connection()


def test_get_postgres_connection_rejects_missing_credentials(
    repository,
    secrets_client,
):
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "postgres_user",
            }
        )
    }

    with pytest.raises(
        ValueError,
        match="PostgreSQL credentials missing from Secrets Manager secret",
    ):
        repository.get_postgres_connection()


def test_get_postgres_connection_requires_db_host(secrets_client):
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "postgres_user",
                "password": "postgres_password",
            }
        )
    }

    with patch.dict("os.environ", {}, clear=True):
        repository = CustomerProfileRepository(
            secret_name="test/secret",
            db_host=None,
            db_name="fintech_fraud",
            secrets_client=secrets_client,
        )

        with pytest.raises(
            ValueError,
            match="DB_HOST environment variable is required",
        ):
            repository.get_postgres_connection()


def test_get_postgres_connection_requires_db_name(secrets_client):
    secrets_client.get_secret_value.return_value = {
        "SecretString": json.dumps(
            {
                "username": "postgres_user",
                "password": "postgres_password",
            }
        )
    }

    with patch.dict("os.environ", {}, clear=True):
        repository = CustomerProfileRepository(
            secret_name="test/secret",
            db_host="localhost",
            db_name=None,
            secrets_client=secrets_client,
        )

        with pytest.raises(
            ValueError,
            match="DB_NAME environment variable is required",
        ):
            repository.get_postgres_connection()


def test_get_profile_returns_none_when_customer_does_not_exist(
    repository,
):
    fake_connection = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.fetchone.return_value = None

    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        repository,
        "get_postgres_connection",
        return_value=fake_connection,
    ):
        result = repository.get_profile(9999)

    assert result is None
    fake_cursor.execute.assert_called_once()
    fake_connection.close.assert_called_once()


def test_get_profile_reconstructs_customer_profile(repository):
    fake_connection = MagicMock()
    fake_cursor = MagicMock()

    row = (
        1001,
        datetime(2026, 9, 1, 10, 0, tzinfo=UTC),
        datetime(2026, 9, 14, 15, 30, tzinfo=UTC),
        3,
        450.75,
        150.25,
        250.0,
        75.75,
        1,
        2,
        ["mobile", "web"],
        ["Lagos", "Abuja"],
        ["card", "bank_transfer"],
        ["Merchant A", "Merchant B"],
        ["10.0.0.1", "10.0.0.2"],
        [
            {
                "transaction_reference": "TXN-001",
                "amount": 100.0,
            }
        ],
    )

    fake_cursor.fetchone.return_value = row
    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        repository,
        "get_postgres_connection",
        return_value=fake_connection,
    ):
        result = repository.get_profile(1001)

    assert isinstance(result, CustomerProfile)
    assert result.customer_id == 1001
    assert result.first_seen == datetime(
        2026, 9, 1, 10, 0, tzinfo=UTC
    )
    assert result.last_seen == datetime(
        2026, 9, 14, 15, 30, tzinfo=UTC
    )
    assert result.total_transactions == 3
    assert result.total_amount == 450.75
    assert result.average_amount == 150.25
    assert result.highest_amount == 250.0
    assert result.lowest_amount == 75.75
    assert result.failed_transactions == 1
    assert result.successful_transactions == 2
    assert result.known_devices == ["mobile", "web"]
    assert result.known_locations == ["Lagos", "Abuja"]
    assert result.known_payment_methods == ["card", "bank_transfer"]
    assert result.known_merchants == ["Merchant A", "Merchant B"]
    assert result.known_ips == ["10.0.0.1", "10.0.0.2"]
    assert result.recent_transactions == [
        {
            "transaction_reference": "TXN-001",
            "amount": 100.0,
        }
    ]

    fake_connection.close.assert_called_once()


def test_create_profile_inserts_default_profile(repository):
    fake_connection = MagicMock()
    fake_cursor = MagicMock()

    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        repository,
        "get_postgres_connection",
        return_value=fake_connection,
    ):
        result = repository.create_profile(1001)

    assert isinstance(result, CustomerProfile)
    assert result.customer_id == 1001
    assert result.total_transactions == 0
    assert result.total_amount == 0.0
    assert result.average_amount == 0.0
    assert result.highest_amount == 0.0
    assert result.lowest_amount == 0.0
    assert result.failed_transactions == 0
    assert result.successful_transactions == 0
    assert result.known_devices == []
    assert result.known_locations == []
    assert result.known_payment_methods == []
    assert result.known_merchants == []
    assert result.known_ips == []
    assert result.recent_transactions == []

    fake_cursor.execute.assert_called_once()

    sql, params = fake_cursor.execute.call_args.args

    normalized_sql = " ".join(sql.split())

    assert "INSERT INTO customers" in normalized_sql
    assert "ON CONFLICT (customer_id) DO NOTHING" in normalized_sql
    assert params[0] == 1001

    fake_connection.close.assert_called_once()


def test_save_writes_complete_profile_as_upsert(
    repository,
    profile,
):
    fake_connection = MagicMock()
    fake_cursor = MagicMock()

    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        repository,
        "get_postgres_connection",
        return_value=fake_connection,
    ):
        repository.save(profile)

    fake_cursor.execute.assert_called_once()

    sql, params = fake_cursor.execute.call_args.args

    normalized_sql = " ".join(sql.split())

    assert "INSERT INTO customers" in normalized_sql
    assert "ON CONFLICT (customer_id) DO UPDATE SET" in normalized_sql
    assert "first_seen = EXCLUDED.first_seen" in normalized_sql
    assert "last_seen = EXCLUDED.last_seen" in normalized_sql
    assert "total_transactions = EXCLUDED.total_transactions" in normalized_sql
    assert "total_amount = EXCLUDED.total_amount" in normalized_sql
    assert "average_amount = EXCLUDED.average_amount" in normalized_sql
    assert "highest_amount = EXCLUDED.highest_amount" in normalized_sql
    assert "lowest_amount = EXCLUDED.lowest_amount" in normalized_sql
    assert "failed_transactions = EXCLUDED.failed_transactions" in normalized_sql
    assert (
        "successful_transactions = EXCLUDED.successful_transactions"
        in normalized_sql
    )
    assert "known_devices = EXCLUDED.known_devices" in normalized_sql
    assert "known_locations = EXCLUDED.known_locations" in normalized_sql
    assert (
        "known_payment_methods = EXCLUDED.known_payment_methods"
        in normalized_sql
    )
    assert "known_merchants = EXCLUDED.known_merchants" in normalized_sql
    assert "known_ips = EXCLUDED.known_ips" in normalized_sql
    assert (
        "recent_transactions = EXCLUDED.recent_transactions"
        in normalized_sql
    )

    assert params[0] == 1001
    assert params[1] == profile.first_seen
    assert params[2] == profile.last_seen
    assert params[3] == 3

    assert params[4] == profile.total_amount
    assert params[5] == profile.average_amount
    assert params[6] == profile.highest_amount
    assert params[7] == profile.lowest_amount

    assert params[8] == 1
    assert params[9] == 2

    assert params[10].adapted == profile.known_devices
    assert params[11].adapted == profile.known_locations
    assert params[12].adapted == profile.known_payment_methods
    assert params[13].adapted == profile.known_merchants
    assert params[14].adapted == profile.known_ips
    assert params[15].adapted == profile.recent_transactions

    fake_connection.close.assert_called_once()


def test_get_or_create_returns_existing_profile(
    repository,
    profile,
):
    with patch.object(
        repository,
        "get_profile",
        return_value=profile,
    ) as get_profile_mock, patch.object(
        repository,
        "create_profile",
    ) as create_profile_mock:
        result = repository.get_or_create(1001)

    assert result is profile
    get_profile_mock.assert_called_once_with(1001)
    create_profile_mock.assert_not_called()


def test_get_or_create_creates_missing_profile(repository):
    created_profile = CustomerProfile(customer_id=1001)

    with patch.object(
        repository,
        "get_profile",
        return_value=None,
    ) as get_profile_mock, patch.object(
        repository,
        "create_profile",
        return_value=created_profile,
    ) as create_profile_mock:
        result = repository.get_or_create(1001)

    assert result is created_profile
    get_profile_mock.assert_called_once_with(1001)
    create_profile_mock.assert_called_once_with(1001)


def test_save_closes_connection_when_database_error_occurs(
    repository,
    profile,
):
    fake_connection = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.execute.side_effect = RuntimeError("database failure")

    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        repository,
        "get_postgres_connection",
        return_value=fake_connection,
    ):
        with pytest.raises(RuntimeError, match="database failure"):
            repository.save(profile)

    fake_connection.close.assert_called_once()


def test_get_profile_closes_connection_when_database_error_occurs(
    repository,
):
    fake_connection = MagicMock()
    fake_cursor = MagicMock()
    fake_cursor.execute.side_effect = RuntimeError("database failure")

    fake_connection.cursor.return_value.__enter__.return_value = fake_cursor

    with patch.object(
        repository,
        "get_postgres_connection",
        return_value=fake_connection,
    ):
        with pytest.raises(RuntimeError, match="database failure"):
            repository.get_profile(1001)

    fake_connection.close.assert_called_once()
