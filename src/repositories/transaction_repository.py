from decimal import Decimal
import logging

from src.models.transaction import Transaction
from src.services.dynamodb import TRANSACTIONS_TABLE

logger = logging.getLogger(__name__)


class TransactionRepository:
    """
    Repository responsible for persisting and retrieving transactions.
    """

    def insert_transaction(
        self,
        transaction: Transaction,
    ) -> str:
        """
        Store a transaction in DynamoDB.

        Returns
        -------
        str
            The transaction reference.
        """

        item = transaction.to_dict()

        #
        # DynamoDB stores Decimal instead of float
        #
        item["amount"] = Decimal(
            str(item["amount"])
        )

        try:

            TRANSACTIONS_TABLE.put_item(
                Item=item
            )

            logger.info(
                "Transaction stored: %s",
                item["transaction_reference"],
            )

            return item["transaction_reference"]

        except Exception:

            logger.exception(
                "Failed to store transaction."
            )

            raise

    def count_transactions(self) -> int:
        """
        Return the total number of stored transactions.
        """

        response = TRANSACTIONS_TABLE.scan(
            Select="COUNT"
        )

        return response["Count"]

    def get_random_customer_id(self) -> int:
        """
        Placeholder until customers are migrated
        to DynamoDB.
        """

        return 1