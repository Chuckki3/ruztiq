from src.repositories.customer_profile_repository import (
    CustomerProfileRepository,
)


class CustomerProfileService:
    """
    Maintains and learns customer behavioural profiles.

    RuztIQ uses these profiles to understand what is
    normal for each customer and identify behavioural changes
    that may indicate fraud.

    The service is responsible for:

    - Building customer transaction history
    - Tracking spending behaviour
    - Tracking known devices
    - Tracking known IP addresses
    - Tracking known locations
    - Tracking known merchants
    - Tracking payment methods
    - Tracking successful and failed transactions
    - Detecting behavioural anomalies
    - Maintaining recent transaction history
    """

    # Maximum number of transactions retained in the profile.
    # The complete transaction history remains in the transactions
    # table; this is only a lightweight behavioural window.
    MAX_RECENT_TRANSACTIONS = 20

    # Minimum history required before amount anomaly detection
    # becomes meaningful.
    MIN_TRANSACTIONS_FOR_AMOUNT_ANOMALY = 10

    # Default multiplier for unusual spending detection.
    DEFAULT_AMOUNT_ANOMALY_MULTIPLIER = 5

    # Failed transaction threshold.
    DEFAULT_FAILED_ATTEMPT_THRESHOLD = 5

    def __init__(self):
        self.repository = CustomerProfileRepository()

    # ==========================================================
    # PROFILE LEARNING
    # ==========================================================

    def learn(self, transaction):
        """
        Learn from a transaction and update the customer's
        behavioural profile.

        The profile becomes progressively richer as RuztIQ
        processes more transactions for the customer.
        """

        profile = self.repository.get_or_create(
            transaction.customer_id
        )

        # ------------------------------------------------------
        # Transaction statistics
        # ------------------------------------------------------

        profile.total_transactions += 1

        profile.total_amount += transaction.amount

        profile.average_amount = (
            profile.total_amount
            / profile.total_transactions
        )

        # ------------------------------------------------------
        # Highest / lowest transaction amount
        # ------------------------------------------------------

        if (
            profile.total_transactions == 1
            or transaction.amount > profile.highest_amount
        ):
            profile.highest_amount = transaction.amount

        if (
            profile.total_transactions == 1
            or transaction.amount < profile.lowest_amount
        ):
            profile.lowest_amount = transaction.amount

        # ------------------------------------------------------
        # First / last seen
        # ------------------------------------------------------

        if profile.first_seen is None:
            profile.first_seen = (
                transaction.transaction_time
            )

        profile.last_seen = (
            transaction.transaction_time
        )

        # ------------------------------------------------------
        # Known devices
        # ------------------------------------------------------

        if (
            transaction.device_type
            not in profile.known_devices
        ):
            profile.known_devices.append(
                transaction.device_type
            )

        # ------------------------------------------------------
        # Known locations
        # ------------------------------------------------------

        if (
            transaction.location
            not in profile.known_locations
        ):
            profile.known_locations.append(
                transaction.location
            )

        # ------------------------------------------------------
        # Known merchants
        # ------------------------------------------------------

        if (
            transaction.merchant_name
            not in profile.known_merchants
        ):
            profile.known_merchants.append(
                transaction.merchant_name
            )

        # ------------------------------------------------------
        # Known IP addresses
        # ------------------------------------------------------

        if (
            transaction.ip_address
            not in profile.known_ips
        ):
            profile.known_ips.append(
                transaction.ip_address
            )

        # ------------------------------------------------------
        # Known payment methods
        #
        # IMPORTANT:
        # CustomerProfile uses known_payment_methods.
        # ------------------------------------------------------

        if (
            transaction.payment_method
            not in profile.known_payment_methods
        ):
            profile.known_payment_methods.append(
                transaction.payment_method
            )

        # ------------------------------------------------------
        # Successful / failed transactions
        # ------------------------------------------------------

        if transaction.status == "FAILED":
            profile.failed_transactions += 1
        else:
            profile.successful_transactions += 1

        # ------------------------------------------------------
        # Recent transaction history
        #
        # Keep this lightweight. Full transaction records remain
        # in DynamoDB's Transactions table.
        # ------------------------------------------------------

        recent_transaction = {
            "transaction_reference": (
                transaction.transaction_reference
            ),
            "amount": transaction.amount,
            "merchant_name": transaction.merchant_name,
            "merchant_category": (
                transaction.merchant_category
            ),
            "transaction_time": (
                transaction.transaction_time.isoformat()
            ),
            "device_type": transaction.device_type,
            "location": transaction.location,
            "ip_address": transaction.ip_address,
            "payment_method": transaction.payment_method,
            "status": transaction.status,
        }

        profile.recent_transactions.append(
            recent_transaction
        )

        # Keep only the most recent transactions.
        profile.recent_transactions = (
            profile.recent_transactions[
                -self.MAX_RECENT_TRANSACTIONS:
            ]
        )

        # ------------------------------------------------------
        # Persist updated profile
        # ------------------------------------------------------

        self.repository.save(profile)

        return profile

    # ==========================================================
    # BEHAVIOURAL SIGNALS
    # ==========================================================

    def is_new_device(
        self,
        profile,
        transaction,
    ):
        """
        Returns True when the customer has never used this
        device before.
        """

        return (
            transaction.device_type
            not in profile.known_devices
        )

    def is_new_location(
        self,
        profile,
        transaction,
    ):
        """
        Returns True when the transaction originates from a
        location never previously associated with the customer.
        """

        return (
            transaction.location
            not in profile.known_locations
        )

    def is_new_ip(
        self,
        profile,
        transaction,
    ):
        """
        Returns True when the IP address has never previously
        been associated with the customer.
        """

        return (
            transaction.ip_address
            not in profile.known_ips
        )

    def is_new_merchant(
        self,
        profile,
        transaction,
    ):
        """
        Returns True when the customer has never previously
        transacted with this merchant.
        """

        return (
            transaction.merchant_name
            not in profile.known_merchants
        )

    def is_new_payment_method(
        self,
        profile,
        transaction,
    ):
        """
        Returns True when the customer is using a payment
        method not previously observed in their profile.
        """

        return (
            transaction.payment_method
            not in profile.known_payment_methods
        )

    # ==========================================================
    # SPENDING ANOMALY
    # ==========================================================

    def is_amount_anomaly(
        self,
        profile,
        transaction,
        multiplier=DEFAULT_AMOUNT_ANOMALY_MULTIPLIER,
    ):
        """
        Detects an unusually large transaction relative to
        the customer's historical spending behaviour.

        Amount anomaly detection only activates after the
        customer has sufficient transaction history.
        """

        if (
            profile.total_transactions
            < self.MIN_TRANSACTIONS_FOR_AMOUNT_ANOMALY
        ):
            return False

        if profile.average_amount <= 0:
            return False

        return (
            transaction.amount
            > profile.average_amount * multiplier
        )

    # ==========================================================
    # FAILED ATTEMPTS
    # ==========================================================

    def has_multiple_failed_attempts(
        self,
        profile,
        threshold=DEFAULT_FAILED_ATTEMPT_THRESHOLD,
    ):
        """
        Returns True when the customer has accumulated an
        unusual number of failed transactions.
        """

        return (
            profile.failed_transactions
            >= threshold
        )

    # ==========================================================
    # PROFILE CHANGE DETECTION
    # ==========================================================

    def get_behavior_signals(
        self,
        profile,
        transaction,
    ):
        """
        Evaluate all customer-profile behavioural signals for
        the current transaction.

        Returns a structured dictionary that can be consumed
        directly by FraudEngine.
        """

        return {
            "new_device": self.is_new_device(
                profile,
                transaction,
            ),
            "new_location": self.is_new_location(
                profile,
                transaction,
            ),
            "new_ip": self.is_new_ip(
                profile,
                transaction,
            ),
            "new_merchant": self.is_new_merchant(
                profile,
                transaction,
            ),
            "new_payment_method": (
                self.is_new_payment_method(
                    profile,
                    transaction,
                )
            ),
            "amount_anomaly": self.is_amount_anomaly(
                profile,
                transaction,
            ),
            "multiple_failed_attempts": (
                self.has_multiple_failed_attempts(
                    profile,
                )
            ),
        }

    # ==========================================================
    # CUSTOMER SUMMARY
    # ==========================================================

    def customer_summary(
        self,
        profile,
    ):
        """
        Return a compact summary of the customer's learned
        behavioural profile.

        Useful for:

        - Fraud explanations
        - API responses
        - Debugging
        - Dashboards
        - Future customer-risk modelling
        """

        return {
            "customer_id": profile.customer_id,
            "total_transactions": (
                profile.total_transactions
            ),
            "total_amount": profile.total_amount,
            "average_amount": profile.average_amount,
            "highest_amount": profile.highest_amount,
            "lowest_amount": profile.lowest_amount,
            "failed_transactions": (
                profile.failed_transactions
            ),
            "successful_transactions": (
                profile.successful_transactions
            ),
            "known_devices": len(
                profile.known_devices
            ),
            "known_locations": len(
                profile.known_locations
            ),
            "known_merchants": len(
                profile.known_merchants
            ),
            "known_ips": len(
                profile.known_ips
            ),
            "known_payment_methods": len(
                profile.known_payment_methods
            ),
            "recent_transactions": len(
                profile.recent_transactions
            ),
        }