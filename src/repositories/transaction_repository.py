from datetime import UTC, datetime, timedelta
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

        The Transaction model is converted into a DynamoDB-
        compatible dictionary before insertion.

        Returns:
            str: The persisted transaction reference.
        """

        item = transaction.to_dict()

        # DynamoDB does not support Python floats directly.
        # Convert monetary values to Decimal.
        if "amount" in item:
            item["amount"] = Decimal(
                str(item["amount"])
            )

        # Store transaction timestamps as ISO-8601 strings.
        if isinstance(
            item.get("transaction_time"),
            datetime,
        ):
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
            This uses Scan and is intended for development
            and operational statistics, not high-volume analytics.
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
            list: Historical transaction dictionaries.
        """

        window_start = (
            transaction_time
            - timedelta(
                minutes=window_minutes
            )
        )

        # Ensure transaction_time is timezone-aware UTC.
        if transaction_time.tzinfo is None:
            transaction_time = (
                transaction_time.replace(
                    tzinfo=UTC
                )
            )

        # Ensure window_start is timezone-aware UTC.
        if window_start.tzinfo is None:
            window_start = (
                window_start.replace(
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

            # Only retrieve history belonging to
            # the customer currently being evaluated.
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

            # Normalise naive timestamps to UTC.
            if historical_time.tzinfo is None:
                historical_time = (
                    historical_time.replace(
                        tzinfo=UTC
                    )
                )

            # Only include transactions inside
            # the configured historical window.
            if (
                window_start
                <= historical_time
                <= transaction_time
            ):
                transactions.append(
                    item
                )

        return transactions