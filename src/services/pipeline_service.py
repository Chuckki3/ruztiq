import logging

from src.fraud.fraud_engine import FraudEngine
from src.generators.transactions_generator import generate_transaction
from src.repositories.fraud_repository import FraudRepository
from src.repositories.transaction_repository import TransactionRepository

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Coordinates the end-to-end fraud detection pipeline.

    Workflow:
        1. Select a random customer
        2. Generate a transaction
        3. Store the transaction
        4. Evaluate fraud risk
        5. Store the fraud result
    """

    def __init__(self):
        self.transaction_repository = TransactionRepository()
        self.fraud_repository = FraudRepository()
        self.fraud_engine = FraudEngine()

    def process_transaction(self):
        """
        Process a single transaction through the pipeline.
        """

        customer_id = self.transaction_repository.get_random_customer_id()

        if customer_id is None:
            logger.warning("No customers found in the database.")
            return None

        transaction = generate_transaction(customer_id)

        transaction_id = self.transaction_repository.insert_transaction(
            transaction
        )

        fraud_result = self.fraud_engine.evaluate(
            transaction=transaction,
            transaction_id=transaction_id,
        )

        self.fraud_repository.insert_result(fraud_result)

        logger.info(
            "Processed transaction %s | Customer=%s | Risk=%s (%s)",
            transaction.transaction_reference,
            customer_id,
            fraud_result.risk_score,
            fraud_result.risk_level,
        )

        return {
            "transaction": transaction,
            "fraud_result": fraud_result,
        }

    def process_batch(self, batch_size=100):
        """
        Process multiple transactions.

        Args:
            batch_size (int): Number of transactions to process.

        Returns:
            int: Number of successfully processed transactions.
        """

        logger.info(
            "Starting batch processing (%s transactions)...",
            batch_size,
        )

        processed = 0

        for _ in range(batch_size):
            result = self.process_transaction()

            if result is not None:
                processed += 1

        logger.info(
            "Batch completed successfully."
        )

        logger.info(
            "Transactions processed: %s",
            processed,
        )

        return processed