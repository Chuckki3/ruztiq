from datetime import datetime
from decimal import Decimal

from src.models.customer_profile import CustomerProfile
from src.services.dynamodb import CUSTOMER_PROFILES_TABLE


class CustomerProfileRepository:
    """
    Handles persistence of customer behavioural profiles
    in DynamoDB.
    """

    # ==========================================================
    # DYNAMODB SERIALIZATION
    # ==========================================================

    @staticmethod
    def _convert_floats_to_decimal(value):
        """
        Recursively convert Python floats to Decimal.

        DynamoDB does not support Python float values.
        This conversion handles floats inside:

        - dictionaries
        - lists
        - tuples
        - nested structures

        Other values are returned unchanged.
        """

        if isinstance(value, float):
            return Decimal(str(value))

        if isinstance(value, dict):
            return {
                key: CustomerProfileRepository._convert_floats_to_decimal(
                    item
                )
                for key, item in value.items()
            }

        if isinstance(value, list):
            return [
                CustomerProfileRepository._convert_floats_to_decimal(
                    item
                )
                for item in value
            ]

        if isinstance(value, tuple):
            return tuple(
                CustomerProfileRepository._convert_floats_to_decimal(
                    item
                )
                for item in value
            )

        return value

    # ==========================================================
    # RETRIEVE PROFILE
    # ==========================================================

    def get_profile(self, customer_id):
        """
        Retrieve an existing customer profile.
        """

        response = CUSTOMER_PROFILES_TABLE.get_item(
            Key={
                "customer_id": customer_id
            }
        )

        item = response.get("Item")

        if not item:
            return None

        # ======================================================
        # DYNAMODB DECIMAL -> PYTHON FLOAT
        # ======================================================

        item["total_amount"] = float(
            item.get("total_amount", 0)
        )

        item["average_amount"] = float(
            item.get("average_amount", 0)
        )

        item["highest_amount"] = float(
            item.get("highest_amount", 0)
        )

        item["lowest_amount"] = float(
            item.get("lowest_amount", 0)
        )

        # ======================================================
        # DYNAMODB NUMBERS
        # ======================================================

        item["total_transactions"] = int(
            item.get("total_transactions", 0)
        )

        item["failed_transactions"] = int(
            item.get("failed_transactions", 0)
        )

        item["successful_transactions"] = int(
            item.get("successful_transactions", 0)
        )

        # ======================================================
        # DATE CONVERSION
        # ======================================================

        first_seen = item.get("first_seen")

        if first_seen:
            item["first_seen"] = datetime.fromisoformat(
                first_seen
            )
        else:
            item["first_seen"] = None

        last_seen = item.get("last_seen")

        if last_seen:
            item["last_seen"] = datetime.fromisoformat(
                last_seen
            )
        else:
            item["last_seen"] = None

        # ======================================================
        # LISTS
        # ======================================================

        item["known_devices"] = item.get(
            "known_devices",
            []
        )

        item["known_locations"] = item.get(
            "known_locations",
            []
        )

        item["known_payment_methods"] = item.get(
            "known_payment_methods",
            []
        )

        item["known_merchants"] = item.get(
            "known_merchants",
            []
        )

        item["known_ips"] = item.get(
            "known_ips",
            []
        )

        item["recent_transactions"] = item.get(
            "recent_transactions",
            []
        )

        return CustomerProfile(**item)

    # ==========================================================
    # CREATE PROFILE
    # ==========================================================

    def create_profile(self, customer_id):
        """
        Create an empty behavioural profile.
        """

        profile = CustomerProfile(
            customer_id=customer_id
        )

        self.save(profile)

        return profile

    # ==========================================================
    # SAVE PROFILE
    # ==========================================================

    def save(self, profile):
        """
        Persist a customer profile to DynamoDB.

        All Python float values are recursively converted
        to Decimal before the DynamoDB write.
        """

        item = profile.to_dict()

        # ======================================================
        # RECURSIVE FLOAT -> DECIMAL CONVERSION
        # ======================================================

        item = self._convert_floats_to_decimal(
            item
        )

        # ======================================================
        # PERSIST
        # ======================================================

        CUSTOMER_PROFILES_TABLE.put_item(
            Item=item
        )

    # ==========================================================
    # GET OR CREATE
    # ==========================================================

    def get_or_create(self, customer_id):
        """
        Retrieve a profile or create one if it does not exist.
        """

        profile = self.get_profile(
            customer_id
        )

        if profile is None:

            profile = self.create_profile(
                customer_id
            )

        return profile