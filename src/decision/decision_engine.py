import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DecisionResult:
    decision: str
    decision_reason: str
    risk_score: int
    risk_level: str
    is_fraud: bool
    velocity_violation: bool


class DecisionEngine:
    """
    Converts RuztIQ fraud and velocity signals into
    an operational transaction decision.

    Decision hierarchy:

        1. Risk score at or above decline threshold
            -> DECLINE

        2. Fraud engine explicitly identifies fraud and
           risk score is at or above review threshold
            -> DECLINE

        3. Velocity violation
            -> REVIEW

        4. Risk score at or above review threshold
            -> REVIEW

        5. Otherwise
            -> APPROVE

    FraudEngine remains responsible for calculating
    fraud risk. DecisionEngine is responsible only for
    authorization policy.
    """

    REVIEW_THRESHOLD = 30
    DECLINE_THRESHOLD = 60

    @classmethod
    def decide(cls, fraud_result, velocity_result=None):
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
                "Invalid fraud risk score: %s. Using 0.",
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

        if risk_score >= cls.DECLINE_THRESHOLD:
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
            and risk_score >= cls.REVIEW_THRESHOLD
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

        elif risk_score >= cls.REVIEW_THRESHOLD:
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

        return DecisionResult(
            decision=decision,
            decision_reason=reason,
            risk_score=risk_score,
            risk_level=risk_level,
            is_fraud=is_fraud,
            velocity_violation=velocity_violation,
        )
