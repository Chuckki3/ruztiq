import os
from datetime import UTC, datetime
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from src.models.customer_profile import CustomerProfile


class CustomerProfileRepository:
    """
    DynamoDB persistence boundary for customer behavioural profiles.

    Customer profiles are stored in the CustomerProfiles table with
    customer_id as the partition key.

    The repository translates between DynamoDB items and the
    CustomerProfile domain model.
    """

    JSON_FIELDS = (
        "known_devices",
        "known_locations",
        "known_payment_methods",
        "known_merchants",
        "known_ips",
        "recent_transactions",
    )

    def __init__(self):
        self.region_name = os.getenv(
            "AWS_REGION_NAME",
            "eu-west-1",
        )
        self.table_name = os.getenv(
            "CUSTOMER_PROFILES_TABLE",
            "CustomerProfiles",
        )

        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=self.region_name,
        )
        self.table = self.dynamodb.Table(self.table_name)

    # ==========================================================
    # DATETIME CONVERSION
    # ==========================================================

    @staticmethod
    def _normalize_datetime(value):
        """
        Normalize datetimes to timezone-aware UTC.
        """
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    @classmethod
    def _datetime_to_string(cls, value):
        """
        Convert a datetime to a normalized UTC ISO-8601 string.
        """
        normalized = cls._normalize_datetime(value)

        if normalized is None:
            return None

        return normalized.isoformat()

    @staticmethod
    def _string_to_datetime(value):
        """
        Convert a stored ISO-8601 string back to datetime.
        """
        if value is None:
            return None

        if isinstance(value, datetime):
            return CustomerProfileRepository._normalize_datetime(
                value
            )

        parsed = datetime.fromisoformat(str(value))

        return CustomerProfileRepository._normalize_datetime(
            parsed
        )

    # ==========================================================
    # DYNAMODB ITEM -> DOMAIN MODEL
    # ==========================================================

    @staticmethod
    def _item_to_profile(item):
        """
        Convert a DynamoDB item into CustomerProfile.
        """
        if item is None:
            return None

        return CustomerProfile(
            customer_id=int(item["customer_id"]),
            first_seen=(
                CustomerProfileRepository._string_to_datetime(
                    item.get("first_seen")
                )
            ),
            last_seen=(
                CustomerProfileRepository._string_to_datetime(
                    item.get("last_seen")
                )
            ),
            total_transactions=int(
                item.get("total_transactions", 0)
            ),
            total_amount=float(
                item.get("total_amount", 0)
            ),
            average_amount=float(
                item.get("average_amount", 0)
            ),
            highest_amount=float(
                item.get("highest_amount", 0)
            ),
            lowest_amount=float(
                item.get("lowest_amount", 0)
            ),
            failed_transactions=int(
                item.get("failed_transactions", 0)
            ),
            successful_transactions=int(
                item.get("successful_transactions", 0)
            ),
            known_devices=list(
                item.get("known_devices", [])
            ),
            known_locations=list(
                item.get("known_locations", [])
            ),
            known_payment_methods=list(
                item.get("known_payment_methods", [])
            ),
            known_merchants=list(
                item.get("known_merchants", [])
            ),
            known_ips=list(
                item.get("known_ips", [])
            ),
            recent_transactions=list(
                item.get("recent_transactions", [])
            ),
        )

    # ==========================================================
    # PROFILE -> DYNAMODB ITEM
    # ==========================================================

    @classmethod
    def _profile_item(cls, profile):
        """
        Convert CustomerProfile into a DynamoDB-compatible item.

        DynamoDB does not accept Python floats. Decimal is therefore
        used for all persisted numeric values.
        """
        item = {
            "customer_id": int(profile.customer_id),
            "total_transactions": int(
                profile.total_transactions
            ),
            "total_amount": Decimal(
                str(profile.total_amount)
            ),
            "average_amount": Decimal(
                str(profile.average_amount)
            ),
            "highest_amount": Decimal(
                str(profile.highest_amount)
            ),
            "lowest_amount": Decimal(
                str(profile.lowest_amount)
            ),
            "failed_transactions": int(
                profile.failed_transactions
            ),
            "successful_transactions": int(
                profile.successful_transactions
            ),
            "known_devices": list(
                profile.known_devices
            ),
            "known_locations": list(
                profile.known_locations
            ),
            "known_payment_methods": list(
                profile.known_payment_methods
            ),
            "known_merchants": list(
                profile.known_merchants
            ),
            "known_ips": list(
                profile.known_ips
            ),
            "recent_transactions": (
                cls._serialize_recent_transactions(
                    profile.recent_transactions
                )
            ),
        }

        first_seen = cls._datetime_to_string(
            profile.first_seen
        )

        if first_seen is not None:
            item["first_seen"] = first_seen

        last_seen = cls._datetime_to_string(
            profile.last_seen
        )

        if last_seen is not None:
            item["last_seen"] = last_seen

        return item

    @staticmethod
    def _serialize_recent_transactions(
        recent_transactions,
    ):
        """
        Convert recent transaction records into DynamoDB-safe
        values, including Decimal conversion for amounts.
        """
        serialized = []

        for transaction in recent_transactions:
            transaction_copy = dict(transaction)

            if "amount" in transaction_copy:
                transaction_copy["amount"] = Decimal(
                    str(transaction_copy["amount"])
                )

            serialized.append(transaction_copy)

        return serialized

    # ==========================================================
    # PROFILE RETRIEVAL
    # ==========================================================

    def get_profile(self, customer_id):
        """
        Retrieve an existing customer profile.

        Returns:
            CustomerProfile | None
        """
        response = self.table.get_item(
            Key={
                "customer_id": int(customer_id),
            }
        )

        return self._item_to_profile(
            response.get("Item")
        )

    # ==========================================================
    # CREATE PROFILE
    # ==========================================================

    def create_profile(self, customer_id):
        """
        Create an empty behavioural profile.

        The conditional write makes creation idempotent and safe
        when concurrent requests attempt to create the same
        customer profile.
        """
        profile = CustomerProfile(
            customer_id=int(customer_id)
        )

        try:
            self.table.put_item(
                Item=self._profile_item(profile),
                ConditionExpression=(
                    "attribute_not_exists(customer_id)"
                ),
            )

            return profile

        except ClientError as exc:
            error_code = exc.response.get(
                "Error",
                {},
            ).get("Code")

            if error_code != "ConditionalCheckFailedException":
                raise

            existing_profile = self.get_profile(
                customer_id
            )

            if existing_profile is None:
                raise

            return existing_profile

    # ==========================================================
    # PROFILE SAVE
    # ==========================================================

    def save(self, profile):
        """
        Persist the complete customer profile.

        A normal PutItem is intentionally used here because the
        service has already loaded and updated the complete profile.
        """
        self.table.put_item(
            Item=self._profile_item(profile)
        )

        return profile

    # ==========================================================
    # GET OR CREATE
    # ==========================================================

    def get_or_create(self, customer_id):
        """
        Retrieve a profile or create one if it does not exist.
        """
        profile = self.get_profile(customer_id)

        if profile is None:
            profile = self.create_profile(
                customer_id
            )

        return profile
