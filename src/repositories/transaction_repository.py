from decimal import Decimal

from src.services.dynamodb import TRANSACTIONS_TABLE


class TransactionRepository:

    def insert_transaction(self, transaction):

        item = transaction.to_dict()

        # DynamoDB stores decimals instead of Python floats
        item["amount"] = Decimal(str(item["amount"]))

        # Store datetime as ISO 8601 string
        item["transaction_time"] = (
            item["transaction_time"].isoformat()
        )

        TRANSACTIONS_TABLE.put_item(Item=item)

        return item["transaction_reference"]

    def count_transactions(self):

        response = TRANSACTIONS_TABLE.scan(
            Select="COUNT"
        )

        return response["Count"]

    def get_random_customer_id(self):
        """
        Placeholder until we migrate customers to DynamoDB.
        """

        return 1