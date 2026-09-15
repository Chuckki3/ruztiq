from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from src.models.transaction import Transaction
from src.repositories.transaction_repository import (
    TransactionRepository,
)


@pytest.fixture
def repository():
    return TransactionRepository()


@pytest.fixture
def transaction():
    return Transaction(
        customer_id=1001,
        transaction_reference="txn-001",
        amount=150.75,
        merchant_name="Test Merchant",
        merchant_category="Retail",
        payment_method="CARD",
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


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_insert_transaction_converts_amount_and_datetime(
    mock_table,
    repository,
    transaction,
):
    result = repository.insert_transaction(transaction)

    mock_table.put_item.assert_called_once()

    item = mock_table.put_item.call_args.kwargs["Item"]

    assert item["transaction_reference"] == "txn-001"
    assert item["customer_id"] == 1001
    assert item["amount"] == Decimal("150.75")
    assert item["transaction_time"] == (
        "2026-09-14T18:30:00+00:00"
    )
    assert result == "txn-001"


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_insert_transaction_propagates_dynamodb_error(
    mock_table,
    repository,
    transaction,
):
    mock_table.put_item.side_effect = RuntimeError(
        "DynamoDB failure"
    )

    with pytest.raises(RuntimeError, match="DynamoDB failure"):
        repository.insert_transaction(transaction)


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_count_transactions_returns_scan_count(
    mock_table,
    repository,
):
    mock_table.scan.return_value = {
        "Count": 17,
    }

    result = repository.count_transactions()

    mock_table.scan.assert_called_once_with(
        Select="COUNT"
    )
    assert result == 17


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_recent_transactions_uses_velocity_gsi(
    mock_table,
    repository,
):
    transaction_time = datetime(
        2026,
        9,
        14,
        18,
        30,
        tzinfo=UTC,
    )

    mock_table.query.return_value = {
        "Items": [],
    }

    result = repository.get_recent_transactions(
        customer_id=1001,
        transaction_time=transaction_time,
        window_minutes=5,
    )

    mock_table.query.assert_called_once_with(
        IndexName="customer_id-transaction_time-index",
        KeyConditionExpression=(
            "customer_id = :customer_id "
            "AND transaction_time BETWEEN :start_time "
            "AND :end_time"
        ),
        ExpressionAttributeValues={
            ":customer_id": 1001,
            ":start_time": (
                "2026-09-14T18:25:00+00:00"
            ),
            ":end_time": (
                "2026-09-14T18:30:00+00:00"
            ),
        },
    )

    assert result == []


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_recent_transactions_reconstructs_transaction(
    mock_table,
    repository,
):
    mock_table.query.return_value = {
        "Items": [
            {
                "customer_id": 1001,
                "transaction_reference": "txn-history-001",
                "amount": Decimal("250.50"),
                "merchant_name": "Example Store",
                "merchant_category": "Retail",
                "payment_method": "CARD",
                "device_type": "Mobile",
                "transaction_time": (
                    "2026-09-14T18:28:00+00:00"
                ),
                "location": "Lagos",
                "ip_address": "10.0.0.1",
                "status": "APPROVED",
            }
        ]
    }

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

    historical = result[0]

    assert isinstance(historical, Transaction)
    assert historical.customer_id == 1001
    assert historical.transaction_reference == (
        "txn-history-001"
    )
    assert historical.amount == 250.50
    assert historical.merchant_name == "Example Store"
    assert historical.transaction_time == datetime(
        2026,
        9,
        14,
        18,
        28,
        tzinfo=UTC,
    )


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_recent_transactions_normalizes_naive_query_time(
    mock_table,
    repository,
):
    mock_table.query.return_value = {
        "Items": [],
    }

    transaction_time = datetime(
        2026,
        9,
        14,
        18,
        30,
    )

    repository.get_recent_transactions(
        customer_id=1001,
        transaction_time=transaction_time,
        window_minutes=5,
    )

    call = mock_table.query.call_args.kwargs

    assert call["ExpressionAttributeValues"] == {
        ":customer_id": 1001,
        ":start_time": (
            "2026-09-14T18:25:00+00:00"
        ),
        ":end_time": (
            "2026-09-14T18:30:00+00:00"
        ),
    }


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_recent_transactions_normalizes_naive_historical_time(
    mock_table,
    repository,
):
    mock_table.query.return_value = {
        "Items": [
            {
                "customer_id": 1001,
                "transaction_reference": "txn-naive-001",
                "amount": Decimal("100.00"),
                "transaction_time": (
                    "2026-09-14T18:28:00"
                ),
            }
        ]
    }

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
    )

    assert len(result) == 1
    assert result[0].transaction_time.tzinfo == UTC


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_recent_transactions_skips_invalid_timestamp(
    mock_table,
    repository,
):
    mock_table.query.return_value = {
        "Items": [
            {
                "customer_id": 1001,
                "transaction_reference": "txn-invalid",
                "amount": Decimal("100.00"),
                "transaction_time": "not-a-timestamp",
            }
        ]
    }

    result = repository.get_recent_transactions(
        customer_id=1001,
        transaction_time=datetime.now(UTC),
    )

    assert result == []


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_recent_transactions_skips_malformed_item(
    mock_table,
    repository,
):
    mock_table.query.return_value = {
        "Items": [
            {
                "customer_id": 1001,
                "amount": Decimal("100.00"),
                "transaction_time": (
                    "2026-09-14T18:28:00+00:00"
                ),
            }
        ]
    }

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
    )

    assert result == []


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_recent_transactions_propagates_query_error(
    mock_table,
    repository,
):
    mock_table.query.side_effect = RuntimeError(
        "DynamoDB query failure"
    )

    with pytest.raises(
        RuntimeError,
        match="DynamoDB query failure",
    ):
        repository.get_recent_transactions(
            customer_id=1001,
            transaction_time=datetime.now(UTC),
        )


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_recent_transactions_handles_multiple_pages(
    mock_table,
    repository,
):
    transaction_time = datetime(
        2026,
        9,
        14,
        18,
        30,
        tzinfo=UTC,
    )

    first_page = {
        "Items": [
            {
                "customer_id": 1001,
                "transaction_reference": "txn-page-001",
                "amount": Decimal("100.00"),
                "transaction_time": (
                    "2026-09-14T18:26:00+00:00"
                ),
            }
        ],
        "LastEvaluatedKey": {
            "transaction_reference": "txn-page-001",
            "customer_id": 1001,
            "transaction_time": (
                "2026-09-14T18:26:00+00:00"
            ),
        },
    }

    second_page = {
        "Items": [
            {
                "customer_id": 1001,
                "transaction_reference": "txn-page-002",
                "amount": Decimal("200.00"),
                "transaction_time": (
                    "2026-09-14T18:27:00+00:00"
                ),
            }
        ]
    }

    mock_table.query.side_effect = [
        first_page,
        second_page,
    ]

    result = repository.get_recent_transactions(
        customer_id=1001,
        transaction_time=transaction_time,
        window_minutes=5,
    )

    assert len(result) == 2

    assert [
        transaction.transaction_reference
        for transaction in result
    ] == [
        "txn-page-001",
        "txn-page-002",
    ]

    assert mock_table.query.call_count == 2

    first_call = mock_table.query.call_args_list[0]
    second_call = mock_table.query.call_args_list[1]

    assert "ExclusiveStartKey" not in first_call.kwargs

    assert second_call.kwargs["ExclusiveStartKey"] == {
        "transaction_reference": "txn-page-001",
        "customer_id": 1001,
        "transaction_time": (
            "2026-09-14T18:26:00+00:00"
        ),
    }


@patch(
    "src.repositories.transaction_repository.TRANSACTIONS_TABLE"
)
def test_get_random_customer_id_returns_synthetic_customer(
    mock_table,
    repository,
):
    result = repository.get_random_customer_id()

    mock_table.assert_not_called()
    assert result == 1
