from datetime import datetime

from src.models.fraud_result import FraudResult


class FraudEngine:
    """
    Rule-based fraud detection engine.

    Evaluates a transaction and returns a FraudResult.
    """

    #
    # Fraud score weights
    #
    HIGH_AMOUNT_SCORE = 30
    LATE_NIGHT_SCORE = 15
    ENTERTAINMENT_SCORE = 10
    HIGH_VALUE_USSD_SCORE = 15
    FAILED_PAYMENT_SCORE = 20

    #
    # Thresholds
    #
    HIGH_AMOUNT_THRESHOLD = 150_000
    HIGH_VALUE_USSD_THRESHOLD = 100_000
    ENTERTAINMENT_AMOUNT_THRESHOLD = 5_000

    #
    # Risk Levels
    #
    HIGH_RISK_THRESHOLD = 60
    MEDIUM_RISK_THRESHOLD = 30
    FRAUD_THRESHOLD = 50

    #
    # Time window
    #
    LATE_NIGHT_START = 0
    LATE_NIGHT_END = 5

    def evaluate(self, transaction) -> FraudResult:
        """
        Evaluate a transaction and return a FraudResult.
        """

        score = 0
        reasons = []

        #
        # High-value transaction
        #
        if transaction.amount > self.HIGH_AMOUNT_THRESHOLD:
            score += self.HIGH_AMOUNT_SCORE
            reasons.append("High Amount")

        #
        # Late-night transaction
        #
        if (
            self.LATE_NIGHT_START
            <= transaction.transaction_time.hour
            <= self.LATE_NIGHT_END
        ):
            score += self.LATE_NIGHT_SCORE
            reasons.append("Late Night")

        #
        # Large entertainment spending
        #
        if (
            transaction.merchant_category == "Entertainment"
            and transaction.amount
            > self.ENTERTAINMENT_AMOUNT_THRESHOLD
        ):
            score += self.ENTERTAINMENT_SCORE
            reasons.append("High Entertainment Spend")

        #
        # High-value USSD transaction
        #
        if (
            transaction.payment_method == "USSD"
            and transaction.amount
            > self.HIGH_VALUE_USSD_THRESHOLD
        ):
            score += self.HIGH_VALUE_USSD_SCORE
            reasons.append("High Value USSD")

        #
        # Failed payment
        #
        if transaction.status == "FAILED":
            score += self.FAILED_PAYMENT_SCORE
            reasons.append("Failed Payment")

        #
        # Risk level
        #
        if score >= self.HIGH_RISK_THRESHOLD:
            risk_level = "HIGH"

        elif score >= self.MEDIUM_RISK_THRESHOLD:
            risk_level = "MEDIUM"

        else:
            risk_level = "LOW"

        return FraudResult(
            transaction_reference=transaction.transaction_reference,
            risk_score=score,
            risk_level=risk_level,
            is_fraud=score >= self.FRAUD_THRESHOLD,
            reasons=(
                ", ".join(reasons)
                if reasons
                else "No suspicious activity"
            ),
            evaluated_at=datetime.utcnow(),
        )