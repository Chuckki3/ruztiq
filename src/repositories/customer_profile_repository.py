import json
import logging
import os
from datetime import datetime

import boto3
import psycopg2
from psycopg2.extras import Json

from src.models.customer_profile import CustomerProfile


logger = logging.getLogger(__name__)


class CustomerProfileRepository:
    """
    PostgreSQL persistence boundary for customer behavioural profiles.

    The repository translates between the CustomerProfile domain model
    and the PostgreSQL `customers` table.

    PostgreSQL is the operational source of truth for customer profiles.
    """

    JSON_FIELDS = (
        "known_devices",
        "known_locations",
        "known_payment_methods",
        "known_merchants",
        "known_ips",
        "recent_transactions",
    )

    def __init__(
        self,
        secret_name=None,
        db_host=None,
        db_port=None,
        db_name=None,
        secrets_client=None,
    ):
        self.secret_name = secret_name or os.environ.get(
            "DB_SECRET_NAME",
            "sentineliq/rds/postgres",
        )
        self.db_host = db_host or os.environ.get("DB_HOST")
        self.db_port = db_port or os.environ.get("DB_PORT", "5432")
        self.db_name = db_name or os.environ.get("DB_NAME")
        self.secrets_client = secrets_client or boto3.client(
            "secretsmanager"
        )

    # ==========================================================
    # POSTGRESQL CONNECTION
    # ==========================================================

    def get_postgres_connection(self):
        """
        Create a PostgreSQL connection using credentials stored in
        AWS Secrets Manager.
        """
        logger.info(
            "Retrieving PostgreSQL credentials from Secrets Manager: %s",
            self.secret_name,
        )

        secret_response = self.secrets_client.get_secret_value(
            SecretId=self.secret_name
        )

        secret_string = secret_response.get("SecretString")

        if not secret_string:
            raise ValueError(
                "Secrets Manager secret does not contain SecretString"
            )

        secret = json.loads(secret_string)

        username = secret.get("username")
        password = secret.get("password")

        if not username or not password:
            raise ValueError(
                "PostgreSQL credentials missing from Secrets Manager secret"
            )

        if not self.db_host:
            raise ValueError("DB_HOST environment variable is required")

        if not self.db_name:
            raise ValueError("DB_NAME environment variable is required")

        logger.info(
            "Connecting to PostgreSQL database '%s' at '%s:%s'",
            self.db_name,
            self.db_host,
            self.db_port,
        )

        return psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=username,
            password=password,
            connect_timeout=10,
        )

    # ==========================================================
    # ROW -> DOMAIN MODEL
    # ==========================================================

    @staticmethod
    def _row_to_profile(row):
        """
        Convert a PostgreSQL customers row into CustomerProfile.
        """
        if row is None:
            return None

        (
            customer_id,
            first_seen,
            last_seen,
            total_transactions,
            total_amount,
            average_amount,
            highest_amount,
            lowest_amount,
            failed_transactions,
            successful_transactions,
            known_devices,
            known_locations,
            known_payment_methods,
            known_merchants,
            known_ips,
            recent_transactions,
        ) = row

        return CustomerProfile(
            customer_id=int(customer_id),
            first_seen=first_seen,
            last_seen=last_seen,
            total_transactions=int(total_transactions or 0),
            total_amount=float(total_amount or 0),
            average_amount=float(average_amount or 0),
            highest_amount=float(highest_amount or 0),
            lowest_amount=float(lowest_amount or 0),
            failed_transactions=int(failed_transactions or 0),
            successful_transactions=int(successful_transactions or 0),
            known_devices=known_devices or [],
            known_locations=known_locations or [],
            known_payment_methods=known_payment_methods or [],
            known_merchants=known_merchants or [],
            known_ips=known_ips or [],
            recent_transactions=recent_transactions or [],
        )

    # ==========================================================
    # PROFILE RETRIEVAL
    # ==========================================================

    def get_profile(self, customer_id):
        """
        Retrieve an existing customer profile.

        Returns:
            CustomerProfile | None
        """
        connection = self.get_postgres_connection()

        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT
                            customer_id,
                            first_seen,
                            last_seen,
                            total_transactions,
                            total_amount,
                            average_amount,
                            highest_amount,
                            lowest_amount,
                            failed_transactions,
                            successful_transactions,
                            known_devices,
                            known_locations,
                            known_payment_methods,
                            known_merchants,
                            known_ips,
                            recent_transactions
                        FROM customers
                        WHERE customer_id = %s
                        """,
                        (customer_id,),
                    )

                    row = cursor.fetchone()

            return self._row_to_profile(row)

        finally:
            connection.close()

    # ==========================================================
    # CREATE PROFILE
    # ==========================================================

    def create_profile(self, customer_id):
        """
        Create an empty behavioural profile.

        The insert is idempotent. If another request creates the
        same customer concurrently, the existing row is retained.
        """
        profile = CustomerProfile(customer_id=customer_id)

        connection = self.get_postgres_connection()

        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO customers (
                            customer_id,
                            first_seen,
                            last_seen,
                            total_transactions,
                            total_amount,
                            average_amount,
                            highest_amount,
                            lowest_amount,
                            failed_transactions,
                            successful_transactions,
                            known_devices,
                            known_locations,
                            known_payment_methods,
                            known_merchants,
                            known_ips,
                            recent_transactions
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        ON CONFLICT (customer_id) DO NOTHING
                        """,
                        self._profile_values(profile),
                    )

            return profile

        finally:
            connection.close()

    # ==========================================================
    # PROFILE SAVE
    # ==========================================================

    def save(self, profile):
        """
        Persist a customer profile.

        The complete profile is written using an upsert so that the
        operation works for both newly-created and existing profiles.
        """
        connection = self.get_postgres_connection()

        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO customers (
                            customer_id,
                            first_seen,
                            last_seen,
                            total_transactions,
                            total_amount,
                            average_amount,
                            highest_amount,
                            lowest_amount,
                            failed_transactions,
                            successful_transactions,
                            known_devices,
                            known_locations,
                            known_payment_methods,
                            known_merchants,
                            known_ips,
                            recent_transactions
                        )
                        VALUES (
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s,
                            %s
                        )
                        ON CONFLICT (customer_id)
                        DO UPDATE SET
                            first_seen = EXCLUDED.first_seen,
                            last_seen = EXCLUDED.last_seen,
                            total_transactions =
                                EXCLUDED.total_transactions,
                            total_amount = EXCLUDED.total_amount,
                            average_amount = EXCLUDED.average_amount,
                            highest_amount = EXCLUDED.highest_amount,
                            lowest_amount = EXCLUDED.lowest_amount,
                            failed_transactions =
                                EXCLUDED.failed_transactions,
                            successful_transactions =
                                EXCLUDED.successful_transactions,
                            known_devices = EXCLUDED.known_devices,
                            known_locations = EXCLUDED.known_locations,
                            known_payment_methods =
                                EXCLUDED.known_payment_methods,
                            known_merchants = EXCLUDED.known_merchants,
                            known_ips = EXCLUDED.known_ips,
                            recent_transactions =
                                EXCLUDED.recent_transactions
                        """,
                        self._profile_values(profile),
                    )

        finally:
            connection.close()

    # ==========================================================
    # GET OR CREATE
    # ==========================================================

    def get_or_create(self, customer_id):
        """
        Retrieve a profile or create one if it does not exist.
        """
        profile = self.get_profile(customer_id)

        if profile is None:
            profile = self.create_profile(customer_id)

        return profile

    # ==========================================================
    # PROFILE -> SQL VALUES
    # ==========================================================

    @classmethod
    def _profile_values(cls, profile):
        """
        Convert CustomerProfile into PostgreSQL query parameters.

        JSON-compatible fields are wrapped with psycopg2.extras.Json
        so PostgreSQL stores them in JSONB columns.
        """
        return (
            profile.customer_id,
            profile.first_seen,
            profile.last_seen,
            profile.total_transactions,
            profile.total_amount,
            profile.average_amount,
            profile.highest_amount,
            profile.lowest_amount,
            profile.failed_transactions,
            profile.successful_transactions,
            Json(profile.known_devices),
            Json(profile.known_locations),
            Json(profile.known_payment_methods),
            Json(profile.known_merchants),
            Json(profile.known_ips),
            Json(profile.recent_transactions),
        )