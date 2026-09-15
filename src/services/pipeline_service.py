import logging

from src.behaviour.velocity_engine import VelocityEngine
from src.decision.decision_engine import DecisionEngine
from src.fraud.fraud_engine import FraudEngine
from src.repositories.fraud_repository import FraudRepository
from src.services.fraud_state_service import FraudStateService
from src.services.metrics_service import MetricsService

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
        Idempotency Check
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
        Atomic Fraud Result Persistence
                ↓
        Learn / Update Customer Profile
                ↓
        Persist Transaction
                ↓
        CloudWatch Metrics
                ↓
        Return Decision

    The customer's profile is evaluated BEFORE the current
    transaction is learned.

    Duplicate transaction references return the previously
    persisted result and do not repeat customer learning or
    transaction persistence.
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
            "velocity_violation": (
                decision_result.velocity_violation
            ),
        }

    # ==========================================================
    # DUPLICATE RESULT
    # ==========================================================

    def _return_existing_result(
        self,
        transaction,
        existing_result,
    ):
        """
        Return an already-persisted transaction result.

        Duplicate requests must not mutate customer state or
        persist the transaction again.
        """
        fraud_result = existing_result["fraud_result"]
        decision = existing_result["decision"]

        logger.info(
            "Returning existing transaction result | "
            "Reference=%s | Decision=%s",
            transaction.transaction_reference,
            decision["decision"],
        )

        return {
            "transaction": transaction,
            "profile": None,
            "velocity": None,
            "fraud_result": fraud_result,
            "decision": decision,
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
        as API Gateway, a fintech transaction API, EventBridge,
        SQS, or an internal service.

        Transaction references act as the idempotency key.

        A previously processed transaction returns its original
        fraud result and decision without repeating customer
        learning or transaction persistence.
        """
        transaction_reference = (
            transaction.transaction_reference
        )

        logger.info(
            "Starting transaction processing | "
            "Reference=%s | Customer=%s",
            transaction_reference,
            transaction.customer_id,
        )

        # ======================================================
        # 1. IDEMPOTENCY CHECK
        # ======================================================

        existing_result = self.fraud_repository.get_result(
            transaction_reference
        )

        if existing_result is not None:
            return self._return_existing_result(
                transaction,
                existing_result,
            )

        # ======================================================
        # 2. LOAD EXISTING CUSTOMER PROFILE
        # ======================================================

        profile = (
            self.fraud_state_service.get_customer_profile(
                transaction.customer_id
            )
        )

        # ======================================================
        # 3. RETRIEVE RECENT TRANSACTION HISTORY
        # ======================================================

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
        # 4. VELOCITY ANALYSIS
        # ======================================================

        velocity_result = self.velocity_engine.score(
            transaction_time=(
                transaction.transaction_time
            ),
            transaction_history=transaction_history,
        )

        # ======================================================
        # 5. FRAUD / BEHAVIOURAL ANALYSIS
        # ======================================================

        fraud_result = self.fraud_engine.evaluate(
            transaction,
            profile,
            velocity_result=velocity_result,
        )

        # ======================================================
        # 6. OPERATIONAL TRANSACTION DECISION
        # ======================================================

        decision = self.determine_decision(
            fraud_result=fraud_result,
            velocity_result=velocity_result,
        )

        # ======================================================
        # 7. ATOMIC FRAUD RESULT PERSISTENCE
        # ======================================================

        stored = (
            self.fraud_repository.insert_result_if_absent(
                result=fraud_result,
                decision=decision,
            )
        )

        # ======================================================
        # 8. CONCURRENT DUPLICATE
        # ======================================================

        if not stored:
            existing_result = (
                self.fraud_repository.get_result(
                    transaction_reference
                )
            )

            if existing_result is None:
                raise RuntimeError(
                    "Fraud result disappeared after "
                    "conditional write conflict: "
                    f"{transaction_reference}"
                )

            return self._return_existing_result(
                transaction,
                existing_result,
            )

        # ======================================================
        # 9. LEARN FROM CURRENT TRANSACTION
        # ======================================================

        updated_profile = (
            self.fraud_state_service.learn_from_transaction(
                transaction
            )
        )

        # ======================================================
        # 10. PERSIST TRANSACTION
        # ======================================================

        self.fraud_state_service.persist_transaction(
            transaction
        )

        # ======================================================
        # 11. CLOUDWATCH METRICS
        # ======================================================

        MetricsService.transaction_processed()

        MetricsService.fraud_score(
            fraud_result.risk_score
        )

        if fraud_result.is_fraud:
            MetricsService.fraud_detected()

        # ======================================================
        # 12. DECISION METRICS
        # ======================================================

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
        # 13. LOGGING
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
        # 14. RETURN COMPLETE PIPELINE RESULT
        # ======================================================

        return {
            "transaction": transaction,
            "profile": updated_profile,
            "velocity": velocity_result,
            "fraud_result": fraud_result,
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

        return self.process_existing_transaction(
            transaction
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