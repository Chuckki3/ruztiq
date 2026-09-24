import os
import random
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import boto3

from src.models.transaction import Transaction


class TransactionRepository:
    """
    DynamoDB-backed repository for RuztIQ transaction persistence
    and behavioural transaction-history queries.

    Transactions are partitioned by customer_id and ordered by a
    composite transaction key:

        <UTC timestamp ISO8601>#<transaction reference>

    This preserves multiple transactions occurring at the same
    timestamp while keeping time-range queries efficient.
    """

    def __init__(self):
        self.region_name = os.getenv(
            "AWS_REGION_NAME",
            "eu-west-1",
        )
        self.table_name = os.getenv(
            "TRANSACTIONS_TABLE",
            "Transactions",
        )

        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=self.region_name,
        )
        self.table = self.dynamodb.Table(self.table_name)

    @staticmethod
    def _normalize_datetime(value):
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    @classmethod
    def _transaction_key(cls, transaction_time, transaction_reference):
        normalized_time = cls._normalize_datetime(
            transaction_time
        )

        return (
            f"{normalized_time.isoformat()}"
            f"#{transaction_reference}"
        )

    @staticmethod
    def _parse_datetime(value):
        if isinstance(value, datetime):
            return TransactionRepository._normalize_datetime(value)

        parsed = datetime.fromisoformat(str(value))

        return TransactionRepository._normalize_datetime(parsed)

    @staticmethod
    def _item_to_transaction(item):
        try:
            historical_time = item.get("transaction_time")

            if historical_time is None:
                return None

            historical_time = TransactionRepository._parse_datetime(
                historical_time
            )

            amount = item.get("amount", 0)

            if isinstance(amount, Decimal):
                amount = float(amount)

            return Transaction(
                customer_id=int(item["customer_id"]),
                transaction_reference=str(
                    item["transaction_reference"]
                ),
                amount=float(amount),
                merchant_name=str(
                    item.get("merchant_name", "")
                ),
                merchant_category=str(
                    item.get("merchant_category", "")
                ),
                payment_method=str(
                    item.get("payment_method", "")
                ),
                device_type=str(
                    item.get("device_type", "")
                ),
                transaction_time=historical_time,
                location=str(item.get("location", "")),
                ip_address=str(item.get("ip_address", "")),
                status=str(
                    item.get("status", "APPROVED")
                ),
            )

        except (TypeError, ValueError, KeyError):
            return None

    def insert_transaction(self, transaction):
        """
        Persist a transaction to DynamoDB.
        """

        transaction_time = self._normalize_datetime(
            transaction.transaction_time
        )

        item = {
            "customer_id": int(transaction.customer_id),
            "transaction_key": self._transaction_key(
                transaction_time,
                transaction.transaction_reference,
            ),
            "transaction_reference": (
                transaction.transaction_reference
            ),
            "amount": Decimal(
                str(transaction.amount)
            ),
            "merchant_name": transaction.merchant_name,
            "merchant_category": transaction.merchant_category,
            "payment_method": transaction.payment_method,
            "device_type": transaction.device_type,
            "transaction_time": transaction_time.isoformat(),
            "location": transaction.location,
            "ip_address": transaction.ip_address,
            "status": transaction.status,
        }

        self.table.put_item(Item=item)

        return transaction.transaction_reference

    def count_transactions(self):
        """
        Return the total number of stored transactions.

        DynamoDB Scan is paginated, so all pages are consumed.
        """

        total = 0
        exclusive_start_key = None

        while True:
            kwargs = {}

            if exclusive_start_key is not None:
                kwargs["ExclusiveStartKey"] = exclusive_start_key

            response = self.table.scan(**kwargs)

            total += int(response.get("Count", 0))

            exclusive_start_key = response.get(
                "LastEvaluatedKey"
            )

            if exclusive_start_key is None:
                break

        return total

    def get_random_customer_id(self):
        """
        Return a customer ID from the transaction population.

        A fallback of 1 is preserved for an empty transaction table.
        """

        response = self.table.scan(
            ProjectionExpression="customer_id",
        )

        customer_ids = {
            int(item["customer_id"])
            for item in response.get("Items", [])
            if item.get("customer_id") is not None
        }

        while response.get("LastEvaluatedKey"):
            response = self.table.scan(
                ProjectionExpression="customer_id",
                ExclusiveStartKey=response[
                    "LastEvaluatedKey"
                ],
            )

            customer_ids.update(
                int(item["customer_id"])
                for item in response.get("Items", [])
                if item.get("customer_id") is not None
            )

        if not customer_ids:
            return 1

        # Preserve the intent of the old random-selection method.
        return random.choice(tuple(customer_ids))

    def get_recent_transactions(
        self,
        customer_id,
        transaction_time,
        window_minutes=5,
    ):
        """
        Retrieve transactions for a customer within the preceding
        time window, ordered chronologically.
        """

        transaction_time = self._normalize_datetime(
            transaction_time
        )

        window_start = (
            transaction_time
            - timedelta(minutes=window_minutes)
        )

        start_key = (
            f"{window_start.isoformat()}#"
        )

        end_key = (
            f"{transaction_time.isoformat()}"
            f"#\uffff"
        )

        response = self.table.query(
            KeyConditionExpression=(
                "customer_id = :customer_id "
                "AND transaction_key BETWEEN "
                ":start_key AND :end_key"
            ),
            ExpressionAttributeValues={
                ":customer_id": int(customer_id),
                ":start_key": start_key,
                ":end_key": end_key,
            },
            ScanIndexForward=True,
        )

        transactions = []

        for item in response.get("Items", []):
            transaction = self._item_to_transaction(item)

            if transaction is not None:
                transactions.append(transaction)

        return transactions