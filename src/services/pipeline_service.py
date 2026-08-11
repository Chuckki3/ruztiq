import logging

from src.fraud.fraud_engine import FraudEngine
from src.generators.transactions_generator import generate_transaction
from src.repositories.fraud_repository import FraudRepository
from src.repositories.transaction_repository import (
    TransactionRepository,
)
from src.profiles.customer_profile_service import (
    CustomerProfileService,
)
from src.services.metrics_service import MetricsService
from src.behaviour.velocity_engine import VelocityEngine


logger = logging.getLogger(__name__)


class PipelineService:
    """
    Coordinates the SentinelIQ fraud detection pipeline.

    Production processing order:

        Incoming Transaction
                ↓
        Load Existing Customer Profile
                ↓
        Retrieve Historical Transactions
                ↓
        Velocity Analysis
                ↓
        Behavioural Fraud Analysis
                ↓
        Persist Fraud Result
                ↓
        Learn / Update Customer Profile
                ↓
        Persist Transaction
                ↓
        CloudWatch Metrics

    IMPORTANT:

    The customer's profile is evaluated BEFORE the current
    transaction is learned.

    This prevents SentinelIQ from accidentally treating a
    suspicious new device, merchant, IP, location, or payment
    method as already trusted.
    """

    def __init__(self):

        self.transaction_repository = (
            TransactionRepository()
        )

        self.fraud_repository = (
            FraudRepository()
        )

        self.profile_service = (
            CustomerProfileService()
        )

        self.fraud_engine = FraudEngine()

        self.velocity_engine = VelocityEngine(
            window_minutes=5,
            transaction_threshold=5,
        )

    # ==========================================================
    # PROCESS EXISTING TRANSACTION
    # ==========================================================

    def process_existing_transaction(
        self,
        transaction,
    ):
        """
        Process a transaction supplied by an external
        source such as:

        - API Gateway
        - fintech transaction API
        - EventBridge
        - SQS
        - internal service
        """

        logger.info(
            "Starting transaction processing | "
            "Reference=%s | Customer=%s",
            transaction.transaction_reference,
            transaction.customer_id,
        )

        # ======================================================
        # 1. LOAD EXISTING CUSTOMER PROFILE
        # ======================================================
        #
        # IMPORTANT:
        # Do this BEFORE learning the current transaction.
        #
        # The fraud engine must see the customer's historical
        # behaviour, not a profile that already contains the
        # transaction being evaluated.
        #

        profile = (
            self.profile_service.repository.get_or_create(
                transaction.customer_id
            )
        )

        # ======================================================
        # 2. RETRIEVE RECENT TRANSACTION HISTORY
        # ======================================================
        #
        # The current transaction has NOT been inserted yet.
        #
        # Therefore this history represents genuine historical
        # activity.
        #

        transaction_history = (
            self.transaction_repository
            .get_recent_transactions(
                customer_id=transaction.customer_id,
                transaction_time=(
                    transaction.transaction_time
                ),
                window_minutes=(
                    self.velocity_engine.window_minutes
                ),
            )
        )

        # ======================================================
        # 3. VELOCITY ANALYSIS
        # ======================================================

        velocity_result = (
            self.velocity_engine.score(
                transaction_time=(
                    transaction.transaction_time
                ),
                transaction_history=(
                    transaction_history
                ),
            )
        )

        # ======================================================
        # 4. FRAUD / BEHAVIOURAL ANALYSIS
        # ======================================================
        #
        # FraudEngine now receives:
        #
        #   transaction
        #   existing customer profile
        #   velocity result
        #
        # The current transaction has not contaminated the
        # customer's behavioural baseline.
        #

        fraud_result = (
            self.fraud_engine.evaluate(
                transaction,
                profile,
                velocity_result=(
                    velocity_result
                ),
            )
        )

        # ======================================================
        # 5. PERSIST FRAUD RESULT
        # ======================================================

        self.fraud_repository.insert_result(
            fraud_result
        )

        # ======================================================
        # 6. LEARN FROM CURRENT TRANSACTION
        # ======================================================
        #
        # ONLY AFTER the fraud decision has been made do we
        # update the customer's behavioural profile.
        #
        # This transaction now becomes part of the customer's
        # future behavioural history.
        #

        updated_profile = (
            self.profile_service.learn(
                transaction
            )
        )

        # ======================================================
        # 7. PERSIST TRANSACTION
        # ======================================================
        #
        # Store the transaction after evaluation.
        #
        # This keeps the historical lookup above clean and
        # prevents the current transaction from counting as
        # previous activity.
        #

        self.transaction_repository.insert_transaction(
            transaction
        )

        # ======================================================
        # 8. CLOUDWATCH METRICS
        # ======================================================

        MetricsService.transaction_processed()

        MetricsService.fraud_score(
            fraud_result.risk_score
        )

        if fraud_result.is_fraud:

            MetricsService.fraud_detected()

        # ======================================================
        # 9. LOGGING
        # ======================================================

        logger.info(
            (
                "Processed %s | "
                "Customer=%s | "
                "Risk=%s (%s) | "
                "Velocity=%s | "
                "RecentTransactions=%s"
            ),
            transaction.transaction_reference,
            transaction.customer_id,
            fraud_result.risk_score,
            fraud_result.risk_level,
            velocity_result.get(
                "is_violation",
                False,
            ),
            velocity_result.get(
                "recent_transactions",
                0,
            ),
        )

        # ======================================================
        # 10. RETURN PIPELINE RESULT
        # ======================================================

        return {
            "transaction": transaction,

            # Return the updated profile because this is now
            # the customer's current behavioural state.
            "profile": updated_profile,

            "velocity": velocity_result,

            "fraud_result": fraud_result,
        }

    # ==========================================================
    # SYNTHETIC TRANSACTION
    # ==========================================================

    def process_generated_transaction(self):
        """
        Generate and process a synthetic transaction.

        Used for development, testing and demonstration.
        """

        customer_id = (
            self.transaction_repository
            .get_random_customer_id()
        )

        transaction = generate_transaction(
            customer_id
        )

        return (
            self.process_existing_transaction(
                transaction
            )
        )

    # ==========================================================
    # BATCH PROCESSING
    # ==========================================================

    def process_batch(
        self,
        batch_size=100,
    ):
        """
        Process a batch of synthetic transactions.
        """

        logger.info(
            "Processing %s transactions...",
            batch_size,
        )

        processed = 0

        for _ in range(batch_size):

            try:

                result = (
                    self.process_generated_transaction()
                )

                if result:

                    processed += 1

            except Exception:

                logger.exception(
                    "Failed to process generated transaction."
                )

        logger.info(
            "Successfully processed %s transactions.",
            processed,
        )

        return processed