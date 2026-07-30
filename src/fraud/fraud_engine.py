from datetime import datetime

from src.models.fraud_result import FraudResult


class FraudEngine:
    """
    Rule-based fraud detection engine.

    Assigns a risk score based on transaction characteristics and
    returns a FraudResult object.
    """

    FRAUD_THRESHOLD = 50

    def evaluate(self, transaction, transaction_id):
        score = 0
        reasons = []

        # High-value transaction
        if transaction.amount > 150000:
            score += 30
            reasons.append("High Amount")

        # Late-night transaction
        if 0 <= transaction.transaction_time.hour <= 5:
            score += 15
            reasons.append("Late Night")

        # Large entertainment spending
        if (
            transaction.merchant_category == "Entertainment"
            and transaction.amount > 5000
        ):
            score += 10
            reasons.append("High Entertainment Spend")

        # High-value USSD transaction
        if (
            transaction.payment_method == "USSD"
            and transaction.amount > 100000
        ):
            score += 15
            reasons.append("High Value USSD")

        # Failed payment
        if transaction.status == "FAILED":
            score += 20
            reasons.append("Failed Payment")

        # Assign risk level
        if score >= 60:
            risk_level = "HIGH"
        elif score >= 30:
            risk_level = "MEDIUM"
        else:
            risk_level = "LOW"

        return FraudResult(
            transaction_id=transaction_id,
            risk_score=score,
            risk_level=risk_level,
            is_fraud=score >= self.FRAUD_THRESHOLD,
            reasons=", ".join(reasons) if reasons else "No suspicious activity",
            evaluated_at=datetime.utcnow(),
        )