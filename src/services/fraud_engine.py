from datetime import time

from src.models.fraud_result import FraudResult


class FraudEngine:

    FRAUD_THRESHOLD = 50

    def score_transaction(self, transaction, transaction_id):

        score = 0
        rules = []

        if transaction.amount > 150000:
            score += 30
            rules.append("High Amount")

        if time(0, 0) <= transaction.transaction_time.time() <= time(5, 0):
            score += 20
            rules.append("Late Night")

        if (
            transaction.payment_method == "Wallet"
            and transaction.amount > 100000
        ):
            score += 15
            rules.append("Large Wallet Payment")

        if (
            transaction.merchant_category == "Entertainment"
            and transaction.amount > 5000
        ):
            score += 15
            rules.append("High Entertainment Spend")

        is_fraud = score >= self.FRAUD_THRESHOLD

        return FraudResult(
            transaction_id=transaction_id,
            risk_score=score,
            is_fraud=is_fraud,
            triggered_rules=", ".join(rules),
        )