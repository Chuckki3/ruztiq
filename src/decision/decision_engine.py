import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DecisionResult:
    decision: str
    risk_score: int
    risk_level: str
    reason: str


class DecisionEngine:
    """
    Converts RuztIQ's fraud risk score into an
    authorization decision.

    Decision policy:

        0-29   -> APPROVE
        30-59  -> REVIEW
        60-100 -> DECLINE

    The decision engine does not calculate fraud risk.
    FraudEngine remains responsible for that.
    """

    APPROVE_MAX_SCORE = 29
    REVIEW_MAX_SCORE = 59
    DECLINE_MIN_SCORE = 60

    @classmethod
    def decide(cls, fraud_result):
        score = int(fraud_result.risk_score)

        if score <= cls.APPROVE_MAX_SCORE:
            decision = "APPROVE"
            reason = "Transaction risk is within the acceptable range."

        elif score <= cls.REVIEW_MAX_SCORE:
            decision = "REVIEW"
            reason = "Transaction requires additional fraud review."

        else:
            decision = "DECLINE"
            reason = "Transaction risk exceeds the authorization threshold."

        logger.info(
            "Authorization decision | transaction=%s | "
            "risk_score=%s | risk_level=%s | decision=%s",
            fraud_result.transaction_reference,
            score,
            fraud_result.risk_level,
            decision,
        )

        return DecisionResult(
            decision=decision,
            risk_score=score,
            risk_level=fraud_result.risk_level,
            reason=reason,
        )
