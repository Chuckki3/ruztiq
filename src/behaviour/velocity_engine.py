from datetime import datetime, timedelta, UTC


class VelocityEngine:
    """
    Detects unusually high transaction frequency for a customer.

    The engine is intentionally independent of DynamoDB and the
    FraudEngine. It receives transaction history and determines
    whether the customer has exceeded a configurable velocity limit.
    """

    DEFAULT_WINDOW_MINUTES = 5
    DEFAULT_TRANSACTION_THRESHOLD = 5

    def __init__(
        self,
        window_minutes=DEFAULT_WINDOW_MINUTES,
        transaction_threshold=DEFAULT_TRANSACTION_THRESHOLD,
    ):
        if window_minutes <= 0:
            raise ValueError(
                "window_minutes must be greater than zero"
            )

        if transaction_threshold <= 0:
            raise ValueError(
                "transaction_threshold must be greater than zero"
            )

        self.window_minutes = window_minutes
        self.transaction_threshold = transaction_threshold

    def count_recent_transactions(
        self,
        transaction_time,
        transaction_history,
    ):
        """
        Count transactions occurring inside the configured
        velocity window ending at transaction_time.

        transaction_history should contain Transaction objects.
        """

        if not transaction_history:
            return 0

        window_start = (
            transaction_time
            - timedelta(minutes=self.window_minutes)
        )

        count = 0

        for transaction in transaction_history:

            transaction_time_value = (
                transaction.transaction_time
            )

            if self._is_within_window(
                transaction_time_value,
                window_start,
                transaction_time,
            ):
                count += 1

        return count

    def is_velocity_violation(
        self,
        transaction_time,
        transaction_history,
    ):
        """
        Return True when transaction velocity reaches
        or exceeds the configured threshold.
        """

        recent_count = self.count_recent_transactions(
            transaction_time,
            transaction_history,
        )

        return (
            recent_count
            >= self.transaction_threshold
        )

    def score(
        self,
        transaction_time,
        transaction_history,
    ):
        """
        Return a velocity risk score and explanation.

        Returns:
            {
                "score": int,
                "recent_transactions": int,
                "is_violation": bool,
                "reason": str | None
            }
        """

        recent_count = self.count_recent_transactions(
            transaction_time,
            transaction_history,
        )

        violation = (
            recent_count
            >= self.transaction_threshold
        )

        if violation:

            return {
                "score": 25,
                "recent_transactions": recent_count,
                "is_violation": True,
                "reason": (
                    "High Transaction Velocity"
                ),
            }

        return {
            "score": 0,
            "recent_transactions": recent_count,
            "is_violation": False,
            "reason": None,
        }

    @staticmethod
    def _is_within_window(
        transaction_time,
        window_start,
        transaction_time_end,
    ):
        """
        Safely compare timezone-aware and naive UTC timestamps.

        This prevents datetime comparison errors while the system
        transitions from legacy datetime.utcnow() usage to
        timezone-aware UTC timestamps.
        """

        if transaction_time.tzinfo is None:

            transaction_time = (
                transaction_time.replace(
                    tzinfo=UTC
                )
            )

        if window_start.tzinfo is None:

            window_start = (
                window_start.replace(
                    tzinfo=UTC
                )
            )

        if transaction_time_end.tzinfo is None:

            transaction_time_end = (
                transaction_time_end.replace(
                    tzinfo=UTC
                )
            )

        return (
            window_start
            <= transaction_time
            <= transaction_time_end
        )