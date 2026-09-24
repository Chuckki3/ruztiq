from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from src.models.transaction import Transaction
from src.repositories.transaction_repository import TransactionRepository


@pytest.fixture
def dynamodb():
    return MagicMock()


@pytest.fixture
def table():
    return MagicMock()


@pytest.fixture
def repository(dynamodb, table):
    with patch(
        "src.repositories.transaction_repository.boto3.resource",
        return_value=dynamodb,
    ):
        dynamodb.Table.return_value = table
        repo = TransactionRepository()

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


def test_repository_uses_dynamodb_table(repository, dynamodb, table):
    dynamodb.Table.assert_called_once_with("Transactions")
    assert repository.table is table


def test_repository_uses_configured_table_name():
    dynamodb = MagicMock()
    table = MagicMock()
    dynamodb.Table.return_value = table

    with patch(
        "src.repositories.transaction_repository.boto3.resource",
        return_value=dynamodb,
    ):
        with patch.dict(
            "os.environ",
            {
                "AWS_REGION_NAME": "eu-west-1",
                "TRANSACTIONS_TABLE": "CustomTransactions",
            },
            clear=False,
        ):
            repo = TransactionRepository()

    dynamodb.Table.assert_called_once_with("CustomTransactions")
    assert repo.table is table


def test_insert_transaction_persists_transaction(
    repository,
    transaction,
):
    result = repository.insert_transaction(transaction)

    assert result == "txn-001"

    repository.table.put_item.assert_called_once()

    item = repository.table.put_item.call_args.kwargs["Item"]

    assert item["customer_id"] == 1001
    assert item["transaction_reference"] == "txn-001"
    assert item["amount"] == Decimal("150.75")
    assert item["merchant_name"] == "Test Merchant"
    assert item["merchant_category"] == "Retail"
    assert item["payment_method"] == "Card"
    assert item["device_type"] == "Mobile"
    assert item["transaction_time"] == (
        "2026-09-14T18:30:00+00:00"
    )
    assert item["location"] == "Lagos"
    assert item["ip_address"] == "192.168.1.10"
    assert item["status"] == "APPROVED"
    assert item["transaction_key"] == (
        "2026-09-14T18:30:00+00:00#txn-001"
    )


def test_insert_transaction_normalizes_naive_datetime(
    repository,
    transaction,
):
    transaction.transaction_time = datetime(
        2026,
        9,
        14,
        18,
        30,
    )

    repository.insert_transaction(transaction)

    item = repository.table.put_item.call_args.kwargs["Item"]

    assert item["transaction_time"] == (
        "2026-09-14T18:30:00+00:00"
    )
    assert item["transaction_key"] == (
        "2026-09-14T18:30:00+00:00#txn-001"
    )


def test_insert_transaction_normalizes_non_utc_datetime(
    repository,
    transaction,
):
    from datetime import timezone

    transaction.transaction_time = datetime(
        2026,
        9,
        14,
        19,
        30,
        tzinfo=timezone(timedelta(hours=1)),
    )

    repository.insert_transaction(transaction)

    item = repository.table.put_item.call_args.kwargs["Item"]

    assert item["transaction_time"] == (
        "2026-09-14T18:30:00+00:00"
    )
    assert item["transaction_key"] == (
        "2026-09-14T18:30:00+00:00#txn-001"
    )


def test_insert_transaction_propagates_dynamodb_error(
    repository,
    transaction,
):
    repository.table.put_item.side_effect = RuntimeError(
        "DynamoDB insert failed"
    )

    with pytest.raises(RuntimeError, match="DynamoDB insert failed"):
        repository.insert_transaction(transaction)


def test_count_transactions_returns_count(
    repository,
):
    repository.table.scan.return_value = {
        "Count": 17,
    }

    assert repository.count_transactions() == 17

    repository.table.scan.assert_called_once_with()


def test_count_transactions_converts_count_to_integer(
    repository,
):
    repository.table.scan.return_value = {
        "Count": "42",
    }

    assert repository.count_transactions() == 42


def test_count_transactions_consumes_all_scan_pages(
    repository,
):
    repository.table.scan.side_effect = [
        {
            "Count": 10,
            "LastEvaluatedKey": {
                "customer_id": 1001,
                "transaction_key": "key-001",
            },
        },
        {
            "Count": 7,
        },
    ]

    assert repository.count_transactions() == 17

    assert repository.table.scan.call_count == 2

    second_call = repository.table.scan.call_args_list[1]

    assert second_call.kwargs["ExclusiveStartKey"] == {
        "customer_id": 1001,
        "transaction_key": "key-001",
    }


def test_get_recent_transactions_queries_velocity_window(
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

    repository.table.query.return_value = {
        "Items": [],
    }

    result = repository.get_recent_transactions(
        customer_id=1001,
        transaction_time=transaction_time,
        window_minutes=5,
    )

    assert result == []

    repository.table.query.assert_called_once()

    kwargs = repository.table.query.call_args.kwargs

    assert kwargs["ExpressionAttributeValues"] == {
        ":customer_id": 1001,
        ":start_key": (
            "2026-09-14T18:25:00+00:00#"
        ),
        ":end_key": (
            "2026-09-14T18:30:00+00:00#\uffff"
        ),
    }

    assert kwargs["ScanIndexForward"] is True


def test_get_recent_transactions_normalizes_naive_query_time(
    repository,
):
    repository.table.query.return_value = {
        "Items": [],
    }

    naive_time = datetime(
        2026,
        9,
        14,
        18,
        30,
    )

    repository.get_recent_transactions(
        customer_id=1001,
        transaction_time=naive_time,
        window_minutes=5,
    )

    kwargs = repository.table.query.call_args.kwargs

    assert kwargs["ExpressionAttributeValues"] == {
        ":customer_id": 1001,
        ":start_key": (
            "2026-09-14T18:25:00+00:00#"
        ),
        ":end_key": (
            "2026-09-14T18:30:00+00:00#\uffff"
        ),
    }


def test_get_recent_transactions_reconstructs_transactions(
    repository,
):
    repository.table.query.return_value = {
        "Items": [
            {
                "customer_id": 1001,
                "transaction_key": (
                    "2026-09-14T18:28:00+00:00#"
                    "txn-history-001"
                ),
                "transaction_reference": "txn-history-001",
                "amount": Decimal("275.50"),
                "merchant_name": "Supermarket",
                "merchant_category": "Groceries",
                "payment_method": "Card",
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

    query_time = datetime(
        2026,
        9,
        14,
        18,
        30,
        tzinfo=UTC,
    )

    result = repository.get_recent_transactions(
        customer_id=1001,
        transaction_time=query_time,
        window_minutes=5,
    )

    assert len(result) == 1

    historical = result[0]

    assert isinstance(historical, Transaction)
    assert historical.customer_id == 1001
    assert historical.transaction_reference == (
        "txn-history-001"
    )
    assert historical.amount == 275.50
    assert historical.merchant_name == "Supermarket"
    assert historical.merchant_category == "Groceries"
    assert historical.payment_method == "Card"
    assert historical.device_type == "Mobile"
    assert historical.transaction_time == datetime(
        2026,
        9,
        14,
        18,
        28,
        tzinfo=UTC,
    )
    assert historical.location == "Lagos"
    assert historical.ip_address == "10.0.0.1"
    assert historical.status == "APPROVED"


def test_get_recent_transactions_skips_missing_timestamp(
    repository,
):
    repository.table.query.return_value = {
        "Items": [
            {
                "customer_id": 1001,
                "transaction_reference": "txn-invalid",
                "amount": Decimal("100.00"),
                "merchant_name": "Merchant",
                "merchant_category": "Retail",
                "payment_method": "Card",
                "device_type": "Mobile",
                "transaction_time": None,
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
    )

    assert result == []


def test_get_recent_transactions_normalizes_naive_historical_time(
    repository,
):
    repository.table.query.return_value = {
        "Items": [
            {
                "customer_id": 1001,
                "transaction_reference": "txn-naive",
                "amount": Decimal("100.00"),
                "merchant_name": "Merchant",
                "merchant_category": "Retail",
                "payment_method": "Card",
                "device_type": "Mobile",
                "transaction_time": (
                    "2026-09-14T18:28:00"
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


def test_get_recent_transactions_skips_malformed_item(
    repository,
):
    repository.table.query.return_value = {
        "Items": [
            {
                "customer_id": "not-an-integer",
                "transaction_reference": "txn-malformed",
                "amount": Decimal("100.00"),
                "merchant_name": "Merchant",
                "merchant_category": "Retail",
                "payment_method": "Card",
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
    )

    assert result == []


def test_get_recent_transactions_propagates_query_error(
    repository,
):
    repository.table.query.side_effect = RuntimeError(
        "DynamoDB query failed"
    )

    with pytest.raises(
        RuntimeError,
        match="DynamoDB query failed",
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
        )


def test_get_random_customer_id_returns_customer_id(
    repository,
):
    repository.table.scan.return_value = {
        "Items": [
            {"customer_id": 1001},
            {"customer_id": 1002},
        ]
    }

    with patch(
        "src.repositories.transaction_repository.random.choice",
        return_value=1001,
    ):
        result = repository.get_random_customer_id()

    assert result == 1001

    kwargs = repository.table.scan.call_args.kwargs

    assert kwargs["ProjectionExpression"] == "customer_id"


def test_get_random_customer_id_falls_back_when_empty(
    repository,
):
    repository.table.scan.return_value = {
        "Items": [],
    }

    assert repository.get_random_customer_id() == 1


def test_get_random_customer_id_consumes_all_scan_pages(
    repository,
):
    repository.table.scan.side_effect = [
        {
            "Items": [{"customer_id": 1001}],
            "LastEvaluatedKey": {
                "customer_id": 1001,
                "transaction_key": "key-001",
            },
        },
        {
            "Items": [{"customer_id": 1002}],
        },
    ]

    with patch(
        "src.repositories.transaction_repository.random.choice",
        return_value=1002,
    ):
        result = repository.get_random_customer_id()

    assert result == 1002
    assert repository.table.scan.call_count == 2

    second_call = repository.table.scan.call_args_list[1]

    assert second_call.kwargs["ExclusiveStartKey"] == {
        "customer_id": 1001,
        "transaction_key": "key-001",
    }
