INSERT_FRAUD_RESULT = """
INSERT INTO fraud_results (
    transaction_id,
    risk_score,
    is_fraud,
    triggered_rules
)
VALUES (
    :transaction_id,
    :risk_score,
    :is_fraud,
    :triggered_rules
);
"""

COUNT_FRAUD_RESULTS = """
SELECT COUNT(*)
FROM fraud_results;
"""