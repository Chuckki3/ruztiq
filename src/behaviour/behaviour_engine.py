class BehaviorEngine:
    """
    RuztIQ behavioural intelligence engine.

    Compares an incoming transaction against the customer's
    previously learned behavioural profile.

    This engine does NOT modify the profile.

    It only observes and produces behavioural signals.
    """

    def __init__(
        self,
        amount_anomaly_multiplier=5,
        failed_attempt_threshold=5,
    ):
        self.amount_anomaly_multiplier = (
            amount_anomaly_multiplier
        )

        self.failed_attempt_threshold = (
            failed_attempt_threshold
        )

    # ==========================================================
    # MAIN ANALYSIS
    # ==========================================================

    def analyze(
        self,
        transaction,
        profile,
    ):
        """
        Analyze the transaction against historical behaviour.

        Returns a structured collection of behavioural signals.
        """

        signals = []

        # ------------------------------------------------------
        # New device
        # ------------------------------------------------------

        if self.is_new_device(
            transaction,
            profile,
        ):
            signals.append(
                "NEW_DEVICE"
            )

        # ------------------------------------------------------
        # New IP
        # ------------------------------------------------------

        if self.is_new_ip(
            transaction,
            profile,
        ):
            signals.append(
                "NEW_IP"
            )

        # ------------------------------------------------------
        # New location
        # ------------------------------------------------------

        if self.is_new_location(
            transaction,
            profile,
        ):
            signals.append(
                "NEW_LOCATION"
            )

        # ------------------------------------------------------
        # New merchant
        # ------------------------------------------------------

        if self.is_new_merchant(
            transaction,
            profile,
        ):
            signals.append(
                "NEW_MERCHANT"
            )

        # ------------------------------------------------------
        # New payment method
        # ------------------------------------------------------

        if self.is_new_payment_method(
            transaction,
            profile,
        ):
            signals.append(
                "NEW_PAYMENT_METHOD"
            )

        # ------------------------------------------------------
        # Amount anomaly
        # ------------------------------------------------------

        if self.is_amount_anomaly(
            transaction,
            profile,
        ):
            signals.append(
                "AMOUNT_ANOMALY"
            )

        # ------------------------------------------------------
        # Failed-attempt behaviour
        # ------------------------------------------------------

        if self.has_multiple_failed_attempts(
            profile,
        ):
            signals.append(
                "MULTIPLE_FAILED_ATTEMPTS"
            )

        return {
            "signals": signals,
            "signal_count": len(signals),
            "is_anomalous": bool(signals),
        }

    # ==========================================================
    # DEVICE
    # ==========================================================

    def is_new_device(
        self,
        transaction,
        profile,
    ):
        """
        Detect a device never previously associated
        with the customer.
        """

        if not transaction.device_type:
            return False

        return (
            transaction.device_type
            not in profile.known_devices
        )

    # ==========================================================
    # IP
    # ==========================================================

    def is_new_ip(
        self,
        transaction,
        profile,
    ):
        """
        Detect an IP address never previously associated
        with the customer.
        """

        if not transaction.ip_address:
            return False

        return (
            transaction.ip_address
            not in profile.known_ips
        )

    # ==========================================================
    # LOCATION
    # ==========================================================

    def is_new_location(
        self,
        transaction,
        profile,
    ):
        """
        Detect a location never previously associated
        with the customer.
        """

        if not transaction.location:
            return False

        return (
            transaction.location
            not in profile.known_locations
        )

    # ==========================================================
    # MERCHANT
    # ==========================================================

    def is_new_merchant(
        self,
        transaction,
        profile,
    ):
        """
        Detect a merchant never previously used
        by the customer.
        """

        if not transaction.merchant_name:
            return False

        return (
            transaction.merchant_name
            not in profile.known_merchants
        )

    # ==========================================================
    # PAYMENT METHOD
    # ==========================================================

    def is_new_payment_method(
        self,
        transaction,
        profile,
    ):
        """
        Detect a payment method never previously used
        by the customer.
        """

        if not transaction.payment_method:
            return False

        return (
            transaction.payment_method
            not in profile.known_payment_methods
        )

    # ==========================================================
    # AMOUNT ANOMALY
    # ==========================================================

    def is_amount_anomaly(
        self,
        transaction,
        profile,
    ):
        """
        Detect unusually large transactions compared
        with the customer's historical spending.

        Requires at least 10 previous transactions.
        """

        if profile.total_transactions < 10:
            return False

        if profile.average_amount <= 0:
            return False

        return (
            float(transaction.amount)
            >
            profile.average_amount
            * self.amount_anomaly_multiplier
        )

    # ==========================================================
    # FAILED ATTEMPTS
    # ==========================================================

    def has_multiple_failed_attempts(
        self,
        profile,
    ):
        """
        Detect accumulated failed transaction behaviour.
        """

        return (
            profile.failed_transactions
            >= self.failed_attempt_threshold
        )