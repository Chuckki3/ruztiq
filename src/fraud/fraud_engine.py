from datetime import datetime, UTC

from src.models.fraud_result import FraudResult


class FraudEngine:
    """
    SentinelIQ fraud detection engine.

    Combines:
    - Transaction-level rules
    - Customer behavioural signals
    - Velocity analysis

    The profile and velocity inputs are optional so that the
    engine remains backwards compatible with existing callers
    and unit tests.
    """

    #
    # Transaction rules
    #

    HIGH_AMOUNT_SCORE = 30
    LATE_NIGHT_SCORE = 15
    ENTERTAINMENT_SCORE = 10
    HIGH_VALUE_USSD_SCORE = 15
    FAILED_PAYMENT_SCORE = 20

    #
    # Behavioural rules
    #

    NEW_DEVICE_SCORE = 20
    NEW_LOCATION_SCORE = 20
    NEW_IP_SCORE = 15
    NEW_MERCHANT_SCORE = 10
    AMOUNT_ANOMALY_SCORE = 30
    MULTIPLE_FAILURE_SCORE = 25

    #
    # Thresholds
    #

    HIGH_AMOUNT_THRESHOLD = 150_000
    HIGH_VALUE_USSD_THRESHOLD = 100_000
    ENTERTAINMENT_AMOUNT_THRESHOLD = 5_000

    HIGH_RISK_THRESHOLD = 60
    MEDIUM_RISK_THRESHOLD = 30
    FRAUD_THRESHOLD = 50

    #
    # Late-night window
    #

    LATE_NIGHT_START = 0
    LATE_NIGHT_END = 5

    def evaluate(
        self,
        transaction,
        profile=None,
        velocity_result=None,
    ):
        """
        Evaluate a transaction.

        Parameters
        ----------
        transaction:
            Transaction object being evaluated.

        profile:
            Optional CustomerProfile containing behavioural
            history.

        velocity_result:
            Optional result produced by VelocityEngine.

        Returns
        -------
        FraudResult
        """

        score = 0
        reasons = []

        #
        # ---------------------------------------------------------
        # 1. HIGH AMOUNT
        # ---------------------------------------------------------
        #

        if (
            transaction.amount
            > self.HIGH_AMOUNT_THRESHOLD
        ):

            score += self.HIGH_AMOUNT_SCORE

            reasons.append(
                "High Amount"
            )

        #
        # ---------------------------------------------------------
        # 2. LATE NIGHT
        # ---------------------------------------------------------
        #

        transaction_hour = (
            transaction.transaction_time.hour
        )

        if (
            self.LATE_NIGHT_START
            <= transaction_hour
            <= self.LATE_NIGHT_END
        ):

            score += self.LATE_NIGHT_SCORE

            reasons.append(
                "Late Night"
            )

        #
        # ---------------------------------------------------------
        # 3. ENTERTAINMENT SPENDING
        # ---------------------------------------------------------
        #

        if (
            transaction.merchant_category
            == "Entertainment"
            and transaction.amount
            > self.ENTERTAINMENT_AMOUNT_THRESHOLD
        ):

            score += self.ENTERTAINMENT_SCORE

            reasons.append(
                "High Entertainment Spend"
            )

        #
        # ---------------------------------------------------------
        # 4. HIGH VALUE USSD
        # ---------------------------------------------------------
        #

        if (
            transaction.payment_method
            == "USSD"
            and transaction.amount
            > self.HIGH_VALUE_USSD_THRESHOLD
        ):

            score += self.HIGH_VALUE_USSD_SCORE

            reasons.append(
                "High Value USSD"
            )

        #
        # ---------------------------------------------------------
        # 5. FAILED PAYMENT
        # ---------------------------------------------------------
        #

        if transaction.status == "FAILED":

            score += self.FAILED_PAYMENT_SCORE

            reasons.append(
                "Failed Payment"
            )

        #
        # ---------------------------------------------------------
        # 6. CUSTOMER BEHAVIOURAL ANALYSIS
        # ---------------------------------------------------------
        #
        # Only execute these rules when a profile exists.
        #

        if profile is not None:

            #
            # New device
            #

            if (
                profile.total_transactions > 1
                and transaction.device_type
                not in profile.known_devices
            ):

                score += self.NEW_DEVICE_SCORE

                reasons.append(
                    "New Device"
                )

            #
            # New location
            #

            if (
                profile.total_transactions > 1
                and transaction.location
                not in profile.known_locations
            ):

                score += self.NEW_LOCATION_SCORE

                reasons.append(
                    "New Location"
                )

            #
            # New IP
            #

            if (
                profile.total_transactions > 1
                and transaction.ip_address
                not in profile.known_ips
            ):

                score += self.NEW_IP_SCORE

                reasons.append(
                    "New IP Address"
                )

            #
            # First-time merchant
            #

            if (
                profile.total_transactions > 1
                and transaction.merchant_name
                not in profile.known_merchants
            ):

                score += self.NEW_MERCHANT_SCORE

                reasons.append(
                    "First-Time Merchant"
                )

            #
            # Spending anomaly
            #
            # Require sufficient history before comparing
            # the current transaction against the customer's
            # normal behaviour.
            #

            if (
                profile.total_transactions >= 10
                and profile.average_amount > 0
                and transaction.amount
                > profile.average_amount * 5
            ):

                score += self.AMOUNT_ANOMALY_SCORE

                reasons.append(
                    "Spending Anomaly"
                )

            #
            # Repeated failed payments
            #

            if (
                profile.failed_transactions >= 5
            ):

                score += (
                    self.MULTIPLE_FAILURE_SCORE
                )

                reasons.append(
                    "Repeated Failed Payments"
                )

        #
        # ---------------------------------------------------------
        # 7. VELOCITY ANALYSIS
        # ---------------------------------------------------------
        #

        if velocity_result is not None:

            velocity_score = (
                velocity_result.get(
                    "score",
                    0,
                )
            )

            score += velocity_score

            if velocity_result.get(
                "is_violation",
                False,
            ):

                reasons.append(
                    velocity_result.get(
                        "reason",
                        "High Transaction Velocity",
                    )
                )

        #
        # ---------------------------------------------------------
        # 8. RISK LEVEL
        # ---------------------------------------------------------

        if score >= self.HIGH_RISK_THRESHOLD:

            risk_level = "HIGH"

        elif score >= self.MEDIUM_RISK_THRESHOLD:

            risk_level = "MEDIUM"

        else:

            risk_level = "LOW"

        #
        # ---------------------------------------------------------
        # 9. FRAUD DECISION
        # ---------------------------------------------------------

        is_fraud = (
            score >= self.FRAUD_THRESHOLD
        )

        #
        # ---------------------------------------------------------
        # 10. RESULT
        # ---------------------------------------------------------

        return FraudResult(
            transaction_reference=(
                transaction.transaction_reference
            ),
            risk_score=score,
            risk_level=risk_level,
            is_fraud=is_fraud,
            reasons=(
                ", ".join(reasons)
                if reasons
                else "No suspicious activity"
            ),
            evaluated_at=datetime.now(UTC),
        )