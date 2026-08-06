from src.fraud.fraud_engine import FraudEngine


def test_normal_transaction(sample_transaction):

    engine = FraudEngine()

    result = engine.evaluate(sample_transaction)

    assert result.risk_score == 30
    assert result.risk_level == "MEDIUM"
    assert result.is_fraud is False


def test_high_risk_transaction(suspicious_transaction):

    engine = FraudEngine()

    result = engine.evaluate(
        suspicious_transaction
    )

    assert result.risk_score == 90
    assert result.risk_level == "HIGH"
    assert result.is_fraud is True

    assert (
        "High Amount"
        in result.reasons
    )

    assert (
        "Failed Payment"
        in result.reasons
    )

    assert (
        "High Entertainment Spend"
        in result.reasons
    )

    assert (
        "High Value USSD"
        in result.reasons
    )