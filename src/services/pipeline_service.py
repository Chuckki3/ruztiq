import logging

from src.fraud.fraud_engine import FraudEngine
from src.generators.transactions_generator import generate_transaction
from src.repositories.fraud_repository import FraudRepository
from src.repositories.transaction_repository import TransactionRepository

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Coordinates the SentinelIQ fraud detection pipeline.
    """

    def __init__(self):
        self.transaction_repository = TransactionRepository()
        self.fraud_repository = FraudRepository()
        self.fraud_engine = FraudEngine()

    def process_transaction(self):

        customer_id = (
            self.transaction_repository.get_random_customer_id()
        )

        transaction = generate_transaction(customer_id)

        self.transaction_repository.insert_transaction(
            transaction
        )

        fraud_result = self.fraud_engine.evaluate(
            transaction
        )

        self.fraud_repository.insert_result(
            fraud_result
        )

        logger.info(
            "Processed %s | Risk=%s (%s)",
            transaction.transaction_reference,
            fraud_result.risk_score,
            fraud_result.risk_level,
        )

        return {
            "transaction": transaction,
            "fraud_result": fraud_result,
        }

    def process_batch(self, batch_size=100):

        logger.info(
            "Processing %s transactions...",
            batch_size,
        )

        processed = 0

        for _ in range(batch_size):

            result = self.process_transaction()

            if result:
                processed += 1

        logger.info(
            "Processed %s transactions.",
            processed,
        )

        return processed