
from datetime import datetime, timedelta, UTC
from decimal import Decimal

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

        item["amount"] = Decimal(
            str(item["amount"])
        )

        item["transaction_time"] = (
            item["transaction_time"].isoformat()
        )

        TRANSACTIONS_TABLE.put_item(
            Item=item
        )

        return item["transaction_reference"]

    def count_transactions(self):
        """
        Return the total number of transactions.

        Note:
        This uses Scan and is intended for development/
        operational statistics, not high-volume analytics.
        """

        response = TRANSACTIONS_TABLE.scan(
            Select="COUNT"
        )

        return response["Count"]

    def get_random_customer_id(self):
        """
        Temporary synthetic-data helper.

        Replace with customer selection logic when
        synthetic transaction generation becomes profile-aware.
        """

        return 1

    def get_recent_transactions(
        self,
        customer_id,
        transaction_time,
        window_minutes=5,
    ):
        """
        Retrieve transactions for a customer within
        a configurable historical time window.

        This method currently uses DynamoDB Scan because
        the existing Transactions table does not yet have
        a customer_id GSI.

        A production migration should add:

            customer_id + transaction_time

        as a DynamoDB access pattern using a GSI.

        Returns:
            List of transaction dictionaries.
        """

        window_start = (
            transaction_time
            - timedelta(
                minutes=window_minutes
            )
        )

        if window_start.tzinfo is None:

            window_start = (
                window_start.replace(
                    tzinfo=UTC
                )
            )

        if transaction_time.tzinfo is None:

            transaction_time = (
                transaction_time.replace(
                    tzinfo=UTC
                )
            )

        response = TRANSACTIONS_TABLE.scan()

        items = response.get(
            "Items",
            [],
        )

        transactions = []

        for item in items:

            if item.get(
                "customer_id"
            ) != customer_id:

                continue

            timestamp = item.get(
                "transaction_time"
            )

            if not timestamp:

                continue

            try:

                historical_time = (
                    datetime.fromisoformat(
                        timestamp
                    )
                )

            except (
                ValueError,
                TypeError,
            ):

                continue

            if historical_time.tzinfo is None:

                historical_time = (
                    historical_time.replace(
                        tzinfo=UTC
                    )
                )

            if (
                window_start
                <= historical_time
                <= transaction_time
            ):

                transactions.append(
                    item
                )

        return transactions
