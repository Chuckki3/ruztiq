import logging

from src.fraud.fraud_engine import FraudEngine
from src.decision.decision_engine import DecisionEngine
from src.repositories.fraud_repository import FraudRepository
from src.services.fraud_state_service import FraudStateService
from src.services.metrics_service import MetricsService
from src.behaviour.velocity_engine import VelocityEngine


logger = logging.getLogger(__name__)


class PipelineService:
    """
    Coordinates the RuztIQ fraud detection pipeline.

    PipelineService owns orchestration.

    It does not directly access the underlying customer-state
    persistence repositories. Operational state is provided through
    FraudStateService.

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
        Transaction Decision
                ↓
        Persist Fraud Result
                ↓
        Learn / Update Customer Profile
                ↓
        Persist Transaction
                ↓
        CloudWatch Metrics
                ↓
        Return Decision

    Decision outcomes:

        APPROVE
            Transaction can proceed automatically.

        REVIEW
            Transaction should be held for additional review.

        DECLINE
            Transaction should be rejected automatically.

    IMPORTANT:

    The customer's profile is evaluated BEFORE the current
    transaction is learned.

    This prevents RuztIQ from accidentally treating a
    suspicious new device, merchant, IP, location, or payment
    method as already trusted.
    """

    def __init__(
        self,
        fraud_state_service=None,
        fraud_repository=None,
    ):
        """
        Initialise the fraud decision pipeline.

        Dependencies are injectable so orchestration can be tested
        independently of the persistence implementation.
        """
        self.fraud_state_service = (
            fraud_state_service
            if fraud_state_service is not None
            else FraudStateService()
        )

        self.fraud_repository = (
            fraud_repository
            if fraud_repository is not None
            else FraudRepository()
        )

        self.fraud_engine = FraudEngine()
        self.decision_engine = DecisionEngine()

        self.velocity_engine = VelocityEngine(
            window_minutes=5,
            transaction_threshold=5,
        )

        logger.info(
            "RuztIQ decision policy | APPROVE < %s | REVIEW %s-%s | DECLINE >= %s",
            DecisionEngine.REVIEW_THRESHOLD,
            DecisionEngine.REVIEW_THRESHOLD,
            DecisionEngine.DECLINE_THRESHOLD - 1,
            DecisionEngine.DECLINE_THRESHOLD,
        )

    # ==========================================================
    # TRANSACTION DECISION ENGINE
    # ==========================================================

    def determine_decision(
        self,
        fraud_result,
        velocity_result,
    ):
        """
        Delegate transaction authorization policy to DecisionEngine.

        PipelineService coordinates the workflow.
        DecisionEngine owns the authorization policy.
        """
        decision_result = self.decision_engine.decide(
            fraud_result=fraud_result,
            velocity_result=velocity_result,
        )

        return {
            "decision": decision_result.decision,
            "decision_reason": decision_result.decision_reason,
            "risk_score": decision_result.risk_score,
            "risk_level": decision_result.risk_level,
            "is_fraud": decision_result.is_fraud,
            "velocity_violation": decision_result.velocity_violation,
        }

    # ==========================================================
    # PROCESS EXISTING TRANSACTION
    # ==========================================================

    def process_existing_transaction(
        self,
        transaction,
    ):
        """
        Process a transaction supplied by an external source such
        as:

        - API Gateway
        - fintech transaction API
        - EventBridge
        - SQS
        - internal service

        The method returns the complete RuztIQ decision package
        while preserving the existing persistence and
        customer-learning behaviour.
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
        #
        # Do this BEFORE learning the current transaction.
        #
        # The fraud engine must see the customer's historical
        # behaviour, not a profile that already contains the
        # transaction being evaluated.
        #

        profile = (
            self.fraud_state_service.get_customer_profile(
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
            self.fraud_state_service.get_recent_transactions(
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
        # FraudEngine receives:
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
        # 5. OPERATIONAL TRANSACTION DECISION
        # ======================================================

        #
        # FraudEngine determines risk.
        # PipelineService converts that risk into an action
        # the fintech can use immediately.
        #

        decision = self.determine_decision(
            fraud_result=fraud_result,
            velocity_result=velocity_result,
        )

        # ======================================================
        # 6. PERSIST FRAUD RESULT
        # ======================================================

        #
        # Preserve the existing fraud repository behaviour.
        #

        self.fraud_repository.insert_result(
            fraud_result
        )

        # ======================================================
        # 7. LEARN FROM CURRENT TRANSACTION
        # ======================================================

        #
        # ONLY AFTER the fraud decision has been made do we
        # update the customer's behavioural profile.
        #
        # This transaction now becomes part of the customer's
        # future behavioural history.
        #

        updated_profile = (
            self.fraud_state_service.learn_from_transaction(
                transaction
            )
        )

        # ======================================================
        # 8. PERSIST TRANSACTION
        # ======================================================

        #
        # Store the transaction after evaluation.
        #
        # This keeps the historical lookup above clean and
        # prevents the current transaction from counting as
        # previous activity.
        #

        self.fraud_state_service.persist_transaction(
            transaction
        )

        # ======================================================
        # 9. CLOUDWATCH METRICS
        # ======================================================

        MetricsService.transaction_processed()

        MetricsService.fraud_score(
            fraud_result.risk_score
        )

        if fraud_result.is_fraud:
            MetricsService.fraud_detected()

        # ======================================================
        # 10. DECISION METRICS
        # ======================================================

        #
        # Only call optional MetricsService methods if they
        # already exist. This prevents the pipeline from breaking
        # if the current MetricsService has not yet been upgraded.
        #

        if hasattr(
            MetricsService,
            "transaction_approved",
        ):
            if decision["decision"] == "APPROVE":
                MetricsService.transaction_approved()

        if hasattr(
            MetricsService,
            "transaction_reviewed",
        ):
            if decision["decision"] == "REVIEW":
                MetricsService.transaction_reviewed()

        if hasattr(
            MetricsService,
            "transaction_declined",
        ):
            if decision["decision"] == "DECLINE":
                MetricsService.transaction_declined()

        # ======================================================
        # 11. LOGGING
        # ======================================================

        logger.info(
            (
                "Processed %s | "
                "Customer=%s | "
                "Risk=%s (%s) | "
                "Decision=%s | "
                "Velocity=%s | "
                "RecentTransactions=%s"
            ),
            transaction.transaction_reference,
            transaction.customer_id,
            fraud_result.risk_score,
            fraud_result.risk_level,
            decision["decision"],
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
        # 12. RETURN COMPLETE PIPELINE RESULT
        # ======================================================

        #
        # Existing return values are preserved.
        #
        # The decision remains available alongside:
        #
        #   transaction
        #   profile
        #   velocity
        #   fraud_result
        #

        return {
            "transaction": transaction,

            # Current behavioural state AFTER learning.
            "profile": updated_profile,

            # Recent behavioural activity observed BEFORE
            # evaluating the transaction.
            "velocity": velocity_result,

            # Original fraud-engine result.
            "fraud_result": fraud_result,

            # Operational authorization decision.
            "decision": decision,
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
            self.fraud_state_service
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

        Returns the number of successfully processed
        transactions.
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