from datetime import datetime, timedelta, UTC

from src.behaviour.velocity_engine import (
    VelocityEngine,
)


class MockTransaction:

    def __init__(self, transaction_time):

        self.transaction_time = (
            transaction_time
        )


def test_velocity_below_threshold():

    now = datetime.now(UTC)

    history = [

        MockTransaction(
            now - timedelta(minutes=1)
        ),

        MockTransaction(
            now - timedelta(minutes=2)
        ),

        MockTransaction(
            now - timedelta(minutes=3)
        ),

    ]

    engine = VelocityEngine(
        window_minutes=5,
        transaction_threshold=5,
    )

    result = engine.score(
        now,
        history,
    )

    assert result["recent_transactions"] == 3
    assert result["is_violation"] is False
    assert result["score"] == 0
    assert result["reason"] is None


def test_velocity_threshold_triggered():

    now = datetime.now(UTC)

    history = [

        MockTransaction(
            now - timedelta(seconds=30)
        ),

        MockTransaction(
            now - timedelta(minutes=1)
        ),

        MockTransaction(
            now - timedelta(minutes=2)
        ),

        MockTransaction(
            now - timedelta(minutes=3)
        ),

        MockTransaction(
            now - timedelta(minutes=4)
        ),

    ]

    engine = VelocityEngine(
        window_minutes=5,
        transaction_threshold=5,
    )

    result = engine.score(
        now,
        history,
    )

    assert result["recent_transactions"] == 5
    assert result["is_violation"] is True
    assert result["score"] == 25
    assert (
        result["reason"]
        == "High Transaction Velocity"
    )


def test_old_transactions_are_ignored():

    now = datetime.now(UTC)

    history = [

        MockTransaction(
            now - timedelta(minutes=10)
        ),

        MockTransaction(
            now - timedelta(minutes=20)
        ),

        MockTransaction(
            now - timedelta(minutes=30)
        ),

    ]

    engine = VelocityEngine(
        window_minutes=5,
        transaction_threshold=3,
    )

    result = engine.score(
        now,
        history,
    )

    assert result["recent_transactions"] == 0
    assert result["is_violation"] is False
    assert result["score"] == 0