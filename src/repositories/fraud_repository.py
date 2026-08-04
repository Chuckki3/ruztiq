from src.services.dynamodb import FRAUD_RESULTS_TABLE


class FraudRepository:

    def insert_result(self, result):

        item = result.to_dict()

        FRAUD_RESULTS_TABLE.put_item(Item=item)

    def count_results(self):

        response = FRAUD_RESULTS_TABLE.scan(
            Select="COUNT"
        )

        return response["Count"]