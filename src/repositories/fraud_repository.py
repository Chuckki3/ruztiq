import logging

from src.models.fraud_result import FraudResult
from src.services.dynamodb import FRAUD_RESULTS_TABLE

logger = logging.getLogger(__name__)


class FraudRepository:
    """
    Repository responsible for persisting fraud
    evaluation results.
    """

    def insert_result(
        self,
        result: FraudResult,
    ) -> None:
        """
        Store a fraud evaluation result in DynamoDB.
        """

        item = result.to_dict()

        try:

            FRAUD_RESULTS_TABLE.put_item(
                Item=item
            )

            logger.info(
                "Fraud result stored: %s",
                result.transaction_reference,
            )

        except Exception:

            logger.exception(
                "Failed to store fraud result."
            )

            raise

    def count_results(self) -> int:
        """
        Return the number of fraud evaluations stored.
        """

        response = FRAUD_RESULTS_TABLE.scan(
            Select="COUNT"
        )

        return response["Count"]