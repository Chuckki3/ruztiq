from types import SimpleNamespace

from src.decision.decision_engine import DecisionEngine


def make_fraud_result(
    risk_score,
    is_fraud=False,
    risk_level="LOW",
):
    return SimpleNamespace(
        risk_score=risk_score,
        risk_level=risk_level,
        is_fraud=is_fraud,
    )


def test_score_below_review_threshold_is_approved():
    result = DecisionEngine.decide(
        make_fraud_result(39)
    )

    assert result.decision == "APPROVE"
    assert result.risk_score == 39
    assert result.is_fraud is False
    assert result.velocity_violation is False


def test_score_at_review_threshold_requires_review():
    result = DecisionEngine.decide(
        make_fraud_result(40)
    )

    assert result.decision == "REVIEW"


def test_score_below_decline_threshold_requires_review():
    result = DecisionEngine.decide(
        make_fraud_result(79)
    )

    assert result.decision == "REVIEW"


def test_score_at_decline_threshold_is_declined():
    result = DecisionEngine.decide(
        make_fraud_result(80)
    )

    assert result.decision == "DECLINE"


def test_confirmed_fraud_above_review_threshold_is_declined():
    result = DecisionEngine.decide(
        make_fraud_result(
            40,
            is_fraud=True,
            risk_level="HIGH",
        )
    )

    assert result.decision == "DECLINE"
    assert result.is_fraud is True


def test_confirmed_fraud_below_review_threshold_is_not_automatically_declined():
    result = DecisionEngine.decide(
        make_fraud_result(
            39,
            is_fraud=True,
            risk_level="LOW",
        )
    )

    assert result.decision == "APPROVE"


def test_velocity_violation_requires_review():
    result = DecisionEngine.decide(
        make_fraud_result(10),
        velocity_result={
            "is_violation": True,
            "recent_transactions": 6,
        },
    )

    assert result.decision == "REVIEW"
    assert result.velocity_violation is True


def test_high_risk_takes_precedence_over_velocity_review():
    result = DecisionEngine.decide(
        make_fraud_result(80),
        velocity_result={
            "is_violation": True,
            "recent_transactions": 6,
        },
    )

    assert result.decision == "DECLINE"


def test_fraud_decline_takes_precedence_over_velocity_review():
    result = DecisionEngine.decide(
        make_fraud_result(
            50,
            is_fraud=True,
            risk_level="HIGH",
        ),
        velocity_result={
            "is_violation": True,
            "recent_transactions": 6,
        },
    )

    assert result.decision == "DECLINE"


def test_invalid_risk_score_defaults_to_zero():
    result = DecisionEngine.decide(
        make_fraud_result("invalid")
    )

    assert result.decision == "APPROVE"
    assert result.risk_score == 0


def test_string_true_is_normalized_to_boolean():
    result = DecisionEngine.decide(
        make_fraud_result(
            50,
            is_fraud="true",
            risk_level="HIGH",
        )
    )

    assert result.decision == "DECLINE"
    assert result.is_fraud is True


def test_decision_reason_is_returned():
    result = DecisionEngine.decide(
        make_fraud_result(80)
    )

    assert result.decision_reason
    assert "decline threshold" in result.decision_reason.lower()
