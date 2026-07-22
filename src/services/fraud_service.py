from datetime import time


class FraudEngine:

    FRAUD_THRESHOLD = 50

    def score_transaction(self, transaction):

        score = 0
        rules = []

        # Rule 1: High-value transaction
        if transaction.amount > 150000:
            score += 30
            rules.append("High Amount")

        # Rule 2: Late-night transaction
        if time(0, 0) <= transaction.transaction_time.time() <= time(5, 0):
            score += 20
            rules.append("Late Night")

        is_fraud = score >= self.FRAUD_THRESHOLD

        return {
            "risk_score": score,
            "is_fraud": is_fraud,
            "triggered_rules": ", ".join(rules),
        }