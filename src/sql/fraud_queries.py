INSERT_FRAUD_RESULT = """
INSERT INTO fraud_results (
    transaction_id,
    risk_score,
    risk_level,
    is_fraud,
    reasons,
    evaluated_at
)
VALUES (
    :transaction_id,
    :risk_score,
    :risk_level,
    :is_fraud,
    :reasons,
    :evaluated_at
);
"""


COUNT_RESULTS = """
SELECT COUNT(*)
FROM fraud_results;
"""