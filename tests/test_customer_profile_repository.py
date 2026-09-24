from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from src.models.customer_profile import CustomerProfile
from src.repositories.customer_profile_repository import (
    CustomerProfileRepository,
)


def make_repository():
    repository = CustomerProfileRepository.__new__(
        CustomerProfileRepository
    )

    repository.region_name = "eu-west-1"
    repository.table_name = "CustomerProfiles"
    repository.dynamodb = MagicMock()
    repository.table = MagicMock()

    return repository


def make_profile():
    return CustomerProfile(
        customer_id=1001,
        first_seen=datetime(
            2026,
            9,
            20,
            10,
            0,
            tzinfo=UTC,
        ),
        last_seen=datetime(
            2026,
            9,
            22,
            15,
            30,
            tzinfo=UTC,
        ),
        total_transactions=12,
        total_amount=15000.50,
        average_amount=1250.0416666667,
        highest_amount=5000.75,
        lowest_amount=50.25,
        failed_transactions=2,
        successful_transactions=10,
        known_devices=["iPhone", "Android"],
        known_locations=["Lagos", "Abuja"],
        known_payment_methods=["CARD", "TRANSFER"],
        known_merchants=["Merchant A", "Merchant B"],
        known_ips=["10.0.0.1", "10.0.0.2"],
        recent_transactions=[
            {
                "transaction_reference": "TX-001",
                "amount": 500.50,
                "merchant_name": "Merchant A",
                "merchant_category": "Retail",
                "transaction_time": (
                    "2026-09-22T15:30:00+00:00"
                ),
                "device_type": "iPhone",
                "location": "Lagos",
                "ip_address": "10.0.0.1",
                "payment_method": "CARD",
                "status": "APPROVED",
            }
        ],
    )


def conditional_failure():
    return ClientError(
        {
            "Error": {
                "Code": "ConditionalCheckFailedException",
                "Message": "Conditional request failed",
            }
        },
        "PutItem",
    )


def test_repository_uses_default_region_and_table(monkeypatch):
    monkeypatch.delenv(
        "AWS_REGION_NAME",
        raising=False,
    )
    monkeypatch.delenv(
        "CUSTOMER_PROFILES_TABLE",
        raising=False,
    )

    mock_resource = MagicMock()

    monkeypatch.setattr(
        "src.repositories.customer_profile_repository.boto3.resource",
        mock_resource,
    )

    repository = CustomerProfileRepository()

    assert repository.region_name == "eu-west-1"
    assert repository.table_name == "CustomerProfiles"

    mock_resource.assert_called_once_with(
        "dynamodb",
        region_name="eu-west-1",
    )


def test_repository_uses_environment_configuration(monkeypatch):
    monkeypatch.setenv(
        "AWS_REGION_NAME",
        "us-east-1",
    )
    monkeypatch.setenv(
        "CUSTOMER_PROFILES_TABLE",
        "CustomCustomerProfiles",
    )

    mock_resource = MagicMock()

    monkeypatch.setattr(
        "src.repositories.customer_profile_repository.boto3.resource",
        mock_resource,
    )

    repository = CustomerProfileRepository()

    assert repository.region_name == "us-east-1"
    assert repository.table_name == (
        "CustomCustomerProfiles"
    )

    mock_resource.assert_called_once_with(
        "dynamodb",
        region_name="us-east-1",
    )


def test_profile_item_converts_numeric_values_to_decimal():
    repository = make_repository()
    profile = make_profile()

    item = repository._profile_item(profile)

    assert item["customer_id"] == 1001
    assert item["total_transactions"] == 12
    assert item["failed_transactions"] == 2
    assert item["successful_transactions"] == 10

    assert item["total_amount"] == Decimal(
        "15000.5"
    )
    assert item["average_amount"] == Decimal(
        "1250.0416666667"
    )
    assert item["highest_amount"] == Decimal(
        "5000.75"
    )
    assert item["lowest_amount"] == Decimal(
        "50.25"
    )


def test_profile_item_serializes_datetimes_to_utc_iso():
    repository = make_repository()
    profile = make_profile()

    item = repository._profile_item(profile)

    assert item["first_seen"] == (
        "2026-09-20T10:00:00+00:00"
    )
    assert item["last_seen"] == (
        "2026-09-22T15:30:00+00:00"
    )


def test_profile_item_normalizes_non_utc_datetime():
    repository = make_repository()

    profile = CustomerProfile(
        customer_id=1001,
        first_seen=datetime.fromisoformat(
            "2026-09-22T18:30:00+01:00"
        ),
        last_seen=datetime.fromisoformat(
            "2026-09-22T18:30:00+01:00"
        ),
    )

    item = repository._profile_item(profile)

    assert item["first_seen"] == (
        "2026-09-22T17:30:00+00:00"
    )
    assert item["last_seen"] == (
        "2026-09-22T17:30:00+00:00"
    )


def test_profile_item_serializes_recent_transaction_amount():
    repository = make_repository()
    profile = make_profile()

    item = repository._profile_item(profile)

    recent = item["recent_transactions"][0]

    assert recent["transaction_reference"] == "TX-001"
    assert recent["amount"] == Decimal("500.5")


def test_item_to_profile_reconstructs_complete_profile():
    repository = make_repository()
    profile = make_profile()

    item = repository._profile_item(profile)

    reconstructed = repository._item_to_profile(item)

    assert reconstructed.customer_id == 1001
    assert reconstructed.first_seen == profile.first_seen
    assert reconstructed.last_seen == profile.last_seen

    assert reconstructed.total_transactions == 12
    assert reconstructed.total_amount == 15000.50
    assert reconstructed.average_amount == (
        1250.0416666667
    )
    assert reconstructed.highest_amount == 5000.75
    assert reconstructed.lowest_amount == 50.25

    assert reconstructed.failed_transactions == 2
    assert reconstructed.successful_transactions == 10

    assert reconstructed.known_devices == [
        "iPhone",
        "Android",
    ]

    assert reconstructed.known_locations == [
        "Lagos",
        "Abuja",
    ]

    assert reconstructed.known_payment_methods == [
        "CARD",
        "TRANSFER",
    ]

    assert reconstructed.known_merchants == [
        "Merchant A",
        "Merchant B",
    ]

    assert reconstructed.known_ips == [
        "10.0.0.1",
        "10.0.0.2",
    ]

    assert len(
        reconstructed.recent_transactions
    ) == 1


def test_item_to_profile_handles_missing_optional_fields():
    repository = make_repository()

    profile = repository._item_to_profile(
        {
            "customer_id": 1001,
        }
    )

    assert profile.customer_id == 1001
    assert profile.first_seen is None
    assert profile.last_seen is None
    assert profile.total_transactions == 0
    assert profile.total_amount == 0
    assert profile.average_amount == 0
    assert profile.highest_amount == 0
    assert profile.lowest_amount == 0
    assert profile.failed_transactions == 0
    assert profile.successful_transactions == 0
    assert profile.known_devices == []
    assert profile.known_locations == []
    assert profile.known_payment_methods == []
    assert profile.known_merchants == []
    assert profile.known_ips == []
    assert profile.recent_transactions == []


def test_get_profile_returns_profile_when_item_exists():
    repository = make_repository()
    profile = make_profile()

    repository.table.get_item.return_value = {
        "Item": repository._profile_item(profile)
    }

    result = repository.get_profile(1001)

    repository.table.get_item.assert_called_once_with(
        Key={"customer_id": 1001}
    )

    assert result.customer_id == 1001


def test_get_profile_returns_none_when_item_missing():
    repository = make_repository()

    repository.table.get_item.return_value = {}

    result = repository.get_profile(1001)

    assert result is None

    repository.table.get_item.assert_called_once_with(
        Key={"customer_id": 1001}
    )


def test_get_profile_converts_customer_id_to_integer():
    repository = make_repository()

    repository.table.get_item.return_value = {
        "Item": {
            "customer_id": Decimal("1001"),
        }
    }

    result = repository.get_profile("1001")

    assert result.customer_id == 1001


def test_create_profile_writes_empty_profile():
    repository = make_repository()

    result = repository.create_profile(1001)

    repository.table.put_item.assert_called_once()

    call_kwargs = (
        repository.table.put_item.call_args.kwargs
    )

    assert call_kwargs["Item"]["customer_id"] == 1001
    assert call_kwargs["Item"]["total_transactions"] == 0
    assert call_kwargs["Item"]["total_amount"] == Decimal(
        "0.0"
    )
    assert call_kwargs["Item"]["average_amount"] == Decimal(
        "0.0"
    )
    assert call_kwargs["Item"]["known_devices"] == []
    assert call_kwargs["Item"]["recent_transactions"] == []

    assert call_kwargs["ConditionExpression"] == (
        "attribute_not_exists(customer_id)"
    )

    assert result.customer_id == 1001


def test_create_profile_returns_existing_profile_on_race():
    repository = make_repository()

    existing = make_profile()

    repository.table.put_item.side_effect = (
        conditional_failure()
    )

    repository.table.get_item.return_value = {
        "Item": repository._profile_item(existing)
    }

    result = repository.create_profile(1001)

    assert result.customer_id == 1001
    assert result.total_transactions == 12

    repository.table.get_item.assert_called_once_with(
        Key={"customer_id": 1001}
    )


def test_create_profile_reraises_conditional_failure_if_profile_missing():
    repository = make_repository()

    repository.table.put_item.side_effect = (
        conditional_failure()
    )

    repository.table.get_item.return_value = {}

    with pytest.raises(ClientError):
        repository.create_profile(1001)


def test_create_profile_reraises_unexpected_client_error():
    repository = make_repository()

    repository.table.put_item.side_effect = ClientError(
        {
            "Error": {
                "Code": "ProvisionedThroughputExceededException",
                "Message": "Capacity exceeded",
            }
        },
        "PutItem",
    )

    with pytest.raises(ClientError):
        repository.create_profile(1001)


def test_save_writes_complete_profile():
    repository = make_repository()
    profile = make_profile()

    result = repository.save(profile)

    repository.table.put_item.assert_called_once()

    call_kwargs = (
        repository.table.put_item.call_args.kwargs
    )

    assert call_kwargs["Item"] == (
        repository._profile_item(profile)
    )

    assert result is profile


def test_save_propagates_dynamodb_errors():
    repository = make_repository()
    profile = make_profile()

    repository.table.put_item.side_effect = RuntimeError(
        "DynamoDB unavailable"
    )

    with pytest.raises(RuntimeError):
        repository.save(profile)


def test_get_or_create_returns_existing_profile():
    repository = make_repository()
    profile = make_profile()

    repository.table.get_item.return_value = {
        "Item": repository._profile_item(profile)
    }

    result = repository.get_or_create(1001)

    assert result.customer_id == 1001
    assert result.total_transactions == 12

    repository.table.put_item.assert_not_called()


def test_get_or_create_creates_missing_profile():
    repository = make_repository()

    repository.table.get_item.return_value = {}

    result = repository.get_or_create(1001)

    assert result.customer_id == 1001

    repository.table.get_item.assert_called_once_with(
        Key={"customer_id": 1001}
    )

    repository.table.put_item.assert_called_once()


def test_get_profile_propagates_dynamodb_error():
    repository = make_repository()

    repository.table.get_item.side_effect = RuntimeError(
        "DynamoDB unavailable"
    )

    with pytest.raises(RuntimeError):
        repository.get_profile(1001)
