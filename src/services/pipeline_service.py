import logging

from src.fraud.fraud_engine import FraudEngine
from src.generators.transactions_generator import generate_transaction
from src.repositories.fraud_repository import FraudRepository
from src.repositories.transaction_repository import TransactionRepository
from src.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class PipelineService:
    """
    Coordinates the SentinelIQ fraud detection pipeline.
    """

    def __init__(self):
        self.transaction_repository = TransactionRepository()
        self.fraud_repository = FraudRepository()
        self.fraud_engine = FraudEngine()

    def process_existing_transaction(self, transaction):
        """
        Process an existing transaction supplied by API Gateway,
        EventBridge, SQS, or another service.
        """

        # Store transaction
        self.transaction_repository.insert_transaction(
            transaction
        )

        # Evaluate fraud
        fraud_result = self.fraud_engine.evaluate(
            transaction
        )

        # Store fraud result
        self.fraud_repository.insert_result(
            fraud_result
        )

        #
        # CloudWatch Metrics
        #
        MetricsService.publish_metric(
            "TransactionsProcessed",
            1,
        )

        MetricsService.publish_metric(
            "FraudScore",
            fraud_result.risk_score,
            unit="None",
        )

        if fraud_result.is_fraud:
            MetricsService.publish_metric(
                "FraudDetected",
                1,
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

    def process_generated_transaction(self):
        """
        Generate a synthetic transaction and process it.
        """

        customer_id = (
            self.transaction_repository.get_random_customer_id()
        )

        transaction = generate_transaction(customer_id)

        return self.process_existing_transaction(
            transaction
        )

    def process_batch(self, batch_size=100):
        """
        Process a batch of generated transactions.
        """

        logger.info(
            "Processing %s transactions...",
            batch_size,
        )

        processed = 0

        for _ in range(batch_size):

            result = (
                self.process_generated_transaction()
            )

            if result:
                processed += 1

        logger.info(
            "Successfully processed %s transactions.",
            processed,
        )

        return processed