import logging
import os

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

        # ======================================================
        # DECISION THRESHOLDS
        # ======================================================
        #
        # These can be overridden through environment variables
        # without changing the application code.
        #
        # Default strategy:
        #
        #   0 - 39  → APPROVE
        #   40 - 79 → REVIEW
        #   80+     → DECLINE
        #
        # The fraud engine remains responsible for calculating
        # the risk score. The pipeline is responsible for turning
        # that score into an operational transaction decision.
        #

        self.review_threshold = self._get_threshold(
            "SENTINELIQ_REVIEW_THRESHOLD",
            40,
        )

        self.decline_threshold = self._get_threshold(
            "SENTINELIQ_DECLINE_THRESHOLD",
            80,
        )

        if self.review_threshold >= self.decline_threshold:
            raise ValueError(
                "SENTINELIQ_REVIEW_THRESHOLD must be lower "
                "than SENTINELIQ_DECLINE_THRESHOLD"
            )

        logger.info(
            "SentinelIQ decision thresholds | "
            "APPROVE < %s | REVIEW %s-%s | DECLINE >= %s",
            self.review_threshold,
            self.review_threshold,
            self.decline_threshold - 1,
            self.decline_threshold,
        )

    # ==========================================================
    # CONFIGURATION HELPERS
    # ==========================================================

    @staticmethod
    def _get_threshold(
        environment_variable,
        default,
    ):
        """
        Read an integer threshold from an environment variable.

        Falls back to the supplied default when the variable is
        missing or invalid.
        """

        value = os.environ.get(
            environment_variable
        )

        if value is None:
            return default

        try:
            return int(value)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid value for %s=%s. "
                "Using default=%s.",
                environment_variable,
                value,
                default,
            )

            return default

    # ==========================================================
    # TRANSACTION DECISION ENGINE
    # ==========================================================

    def determine_decision(
        self,
        fraud_result,
        velocity_result,
    ):
        """
        Convert the fraud engine result into an operational
        transaction decision.

        Returns a dictionary containing:

            decision
            decision_reason
            risk_score
            risk_level
            is_fraud
            velocity_violation

        Decision hierarchy:

            1. Critical/high risk at or above decline threshold
               → DECLINE

            2. Fraud engine explicitly identifies fraud
               and the score is at or above the review threshold
               → DECLINE

            3. Risk score at or above review threshold
               → REVIEW

            4. Otherwise
               → APPROVE

        The velocity engine is also considered so that a strong
        velocity violation cannot silently pass as an ordinary
        low-risk transaction.
        """

        risk_score = getattr(
            fraud_result,
            "risk_score",
            0,
        )

        risk_level = getattr(
            fraud_result,
            "risk_level",
            None,
        )

        is_fraud = getattr(
            fraud_result,
            "is_fraud",
            False,
        )

        try:
            risk_score = int(risk_score)
        except (TypeError, ValueError):
            logger.warning(
                "Invalid fraud risk score: %s. "
                "Using 0.",
                risk_score,
            )
            risk_score = 0

        if isinstance(is_fraud, str):
            is_fraud = (
                is_fraud.lower() == "true"
            )

        if not isinstance(is_fraud, bool):
            is_fraud = bool(is_fraud)

        velocity_violation = False

        if isinstance(velocity_result, dict):
            velocity_violation = bool(
                velocity_result.get(
                    "is_violation",
                    False,
                )
            )

        # ======================================================
        # 1. HARD DECLINE
        # ======================================================

        if risk_score >= self.decline_threshold:
            decision = "DECLINE"

            reason = (
                "Risk score exceeds the automatic "
                "decline threshold."
            )

        # ======================================================
        # 2. CONFIRMED FRAUD
        # ======================================================

        elif (
            is_fraud
            and risk_score >= self.review_threshold
        ):
            decision = "DECLINE"

            reason = (
                "Fraud engine identified the transaction "
                "as fraudulent."
            )

        # ======================================================
        # 3. VELOCITY REVIEW
        # ======================================================

        elif velocity_violation:
            decision = "REVIEW"

            reason = (
                "Transaction velocity exceeded the "
                "configured behavioural threshold."
            )

        # ======================================================
        # 4. RISK REVIEW
        # ======================================================

        elif risk_score >= self.review_threshold:
            decision = "REVIEW"

            reason = (
                "Risk score requires additional review."
            )

        # ======================================================
        # 5. APPROVE
        # ======================================================

        else:
            decision = "APPROVE"

            reason = (
                "Transaction is below the configured "
                "review threshold."
            )

        result = {
            "decision": decision,
            "decision_reason": reason,
            "risk_score": risk_score,
            "risk_level": risk_level,
            "is_fraud": is_fraud,
            "velocity_violation": velocity_violation,
        }

        logger.info(
            "Transaction decision | "
            "Decision=%s | "
            "RiskScore=%s | "
            "RiskLevel=%s | "
            "Fraud=%s | "
            "VelocityViolation=%s | "
            "Reason=%s",
            decision,
            risk_score,
            risk_level,
            is_fraud,
            velocity_violation,
            reason,
        )

        return result

    # ==========================================================
    # PROCESS EXISTING TRANSACTION
    # ==========================================================

    def process_existing_transaction(
        self,
        transaction,
    ):
        """
        Process a transaction supplied by an external source
        such as:

        - API Gateway
        - fintech transaction API
        - EventBridge
        - SQS
        - internal service

        The method returns the complete SentinelIQ decision
        package while preserving the existing persistence and
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
        # This is the new layer.
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
            self.profile_service.learn(
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

        self.transaction_repository.insert_transaction(
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
        # IMPORTANT:
        #
        # The existing return values are preserved.
        #
        # We are only adding:
        #
        #     "decision"
        #
        # This means existing callers that use transaction,
        # profile, velocity or fraud_result continue to work.
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

            # New operational authorization decision.
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