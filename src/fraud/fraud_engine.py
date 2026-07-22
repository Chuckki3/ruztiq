from datetime import datetime

from src.models.fraud_result import FraudResult


class FraudEngine:

    def evaluate(self, transaction, transaction_id=0):

        score = 0
        reasons = []

        # High amount
        if transaction.amount >= 500000:
            score += 40
            reasons.append("High transaction amount")

        # Failed transaction
        if transaction.transaction_status == "FAILED":
            score += 20
            reasons.append("Failed payment")

        # Crypto payment
        if transaction.payment_method == "Crypto":
            score += 15
            reasons.append("Crypto payment")

        # Late night
        hour = transaction.transaction_time.hour

        if hour < 5:
            score += 15
            reasons.append("Late night transaction")

        # High-risk merchant categories
        risky_categories = {
            "Crypto",
            "Gaming",
            "Betting",
        }

        if transaction.merchant_category in risky_categories:
            score += 10
            reasons.append("High-risk merchant")

        if score >= 60:
            level = "HIGH"
        elif score >= 30:
            level = "MEDIUM"
        else:
            level = "LOW"

        return FraudResult(
            transaction_id=transaction_id,
            risk_score=score,
            risk_level=level,
            is_fraud=score >= 60,
            reasons=", ".join(reasons),
            evaluated_at=datetime.utcnow(),
        )