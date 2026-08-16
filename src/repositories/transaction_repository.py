from datetime import UTC, datetime, timedelta
from decimal import Decimal

from src.models.transaction import Transaction
from src.services.dynamodb import TRANSACTIONS_TABLE


class TransactionRepository:
    """
    Repository for SentinelIQ transaction persistence
    and behavioural transaction-history queries.
    """

    def insert_transaction(self, transaction):
        """
        Persist a transaction to DynamoDB.
        """

        item = transaction.to_dict()

        if "amount" in item:
            item["amount"] = Decimal(str(item["amount"]))

        if isinstance(item.get("transaction_time"), datetime):
            item["transaction_time"] = item["transaction_time"].isoformat()

        TRANSACTIONS_TABLE.put_item(Item=item)

        return item["transaction_reference"]

    def count_transactions(self):
        """
        Return the total number of transactions.

        Uses Scan for development and operational statistics.
        """

        response = TRANSACTIONS_TABLE.scan(
            Select="COUNT"
        )

        return response["Count"]

    def get_random_customer_id(self):
        """
        Temporary synthetic-data helper.
        """

        return 1

    def get_recent_transactions(
        self,
        customer_id,
        transaction_time,
        window_minutes=5,
    ):
        """
        Retrieve historical transactions for a customer
        within the configured velocity window.

        Uses the customer_id + transaction_time GSI.
        """

        if transaction_time.tzinfo is None:
            transaction_time = transaction_time.replace(
                tzinfo=UTC
            )

        window_start = (
            transaction_time
            - timedelta(minutes=window_minutes)
        )

        response = TRANSACTIONS_TABLE.query(
            IndexName="customer_id-transaction_time-index",
            KeyConditionExpression=(
                "customer_id = :customer_id "
                "AND transaction_time BETWEEN :start_time "
                "AND :end_time"
            ),
            ExpressionAttributeValues={
                ":customer_id": customer_id,
                ":start_time": window_start.isoformat(),
                ":end_time": transaction_time.isoformat(),
            },
        )

        items = response.get("Items", [])

        transactions = []

        for item in items:
            timestamp = item.get("transaction_time")

            if not timestamp:
                continue

            try:
                historical_time = datetime.fromisoformat(
                    timestamp
                )
            except (ValueError, TypeError):
                continue

            if historical_time.tzinfo is None:
                historical_time = historical_time.replace(
                    tzinfo=UTC
                )

            amount = item.get("amount", 0)

            if isinstance(amount, Decimal):
                amount = float(amount)

            try:
                transaction = Transaction(
                    customer_id=int(
                        item["customer_id"]
                    ),
                    transaction_reference=str(
                        item["transaction_reference"]
                    ),
                    amount=amount,
                    merchant_name=str(
                        item.get(
                            "merchant_name",
                            "",
                        )
                    ),
                    merchant_category=str(
                        item.get(
                            "merchant_category",
                            "",
                        )
                    ),
                    payment_method=str(
                        item.get(
                            "payment_method",
                            "",
                        )
                    ),
                    device_type=str(
                        item.get(
                            "device_type",
                            "",
                        )
                    ),
                    transaction_time=historical_time,
                    location=str(
                        item.get(
                            "location",
                            "",
                        )
                    ),
                    ip_address=str(
                        item.get(
                            "ip_address",
                            "",
                        )
                    ),
                    status=str(
                        item.get(
                            "status",
                            "APPROVED",
                        )
                    ),
                )

            except (
                KeyError,
                TypeError,
                ValueError,
            ):
                continue

            transactions.append(transaction)

        return transactions
