import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import boto3
import psycopg2

from src.models.transaction import Transaction


class TransactionRepository:
    """
    PostgreSQL-backed repository for RuztIQ transaction persistence
    and behavioural transaction-history queries.
    """

    def __init__(self):
        self.secret_name = os.getenv(
            "DB_SECRET_NAME",
            "sentineliq/rds/postgres",
        )
        self.db_host = os.getenv("DB_HOST")
        self.db_port = int(
            os.getenv("DB_PORT", "5432")
        )
        self.db_name = os.getenv(
            "DB_NAME",
            "fintech_fraud",
        )
        self.region_name = os.getenv(
            "AWS_REGION_NAME",
            "eu-west-1",
        )

        self.secrets_client = boto3.client(
            "secretsmanager",
            region_name=self.region_name,
        )

    def _get_connection(self):
        """
        Create a PostgreSQL connection using credentials
        stored in AWS Secrets Manager.
        """
        response = self.secrets_client.get_secret_value(
            SecretId=self.secret_name
        )
        secret = response["SecretString"]

        import json

        credentials = json.loads(secret)

        return psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=credentials["username"],
            password=credentials["password"],
            connect_timeout=10,
        )

    @staticmethod
    def _normalize_datetime(value):
        """
        Normalize timestamps to timezone-aware UTC datetimes.
        """
        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    def insert_transaction(self, transaction):
        """
        Persist a transaction to PostgreSQL.
        """
        transaction_time = self._normalize_datetime(
            transaction.transaction_time
        )

        query = """
            INSERT INTO transactions (
                transaction_reference,
                customer_id,
                amount,
                merchant_name,
                merchant_category,
                payment_method,
                device_type,
                transaction_time,
                location,
                ip_address,
                status
            )
            VALUES (
                %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s
            )
        """

        params = (
            transaction.transaction_reference,
            transaction.customer_id,
            Decimal(str(transaction.amount)),
            transaction.merchant_name,
            transaction.merchant_category,
            transaction.payment_method,
            transaction.device_type,
            transaction_time,
            transaction.location,
            transaction.ip_address,
            transaction.status,
        )

        connection = self._get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(query, params)

            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

        return transaction.transaction_reference

    def count_transactions(self):
        """
        Return the total number of persisted transactions.
        """
        query = """
            SELECT COUNT(*)
            FROM transactions
        """

        connection = self._get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()

            return int(row[0])
        finally:
            connection.close()

    def get_random_customer_id(self):
        """
        Return a customer ID from the transactions table.

        This preserves the existing synthetic-data helper contract
        while sourcing the value from PostgreSQL.
        """
        query = """
            SELECT customer_id
            FROM transactions
            ORDER BY RANDOM()
            LIMIT 1
        """

        connection = self._get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(query)
                row = cursor.fetchone()

            if row is None:
                return 1

            return int(row[0])
        finally:
            connection.close()

    def get_recent_transactions(
        self,
        customer_id,
        transaction_time,
        window_minutes=5,
    ):
        """
        Retrieve historical transactions for a customer within
        the configured velocity window.

        PostgreSQL uses the existing
        (customer_id, transaction_time) index.
        """
        transaction_time = self._normalize_datetime(
            transaction_time
        )

        window_start = (
            transaction_time
            - timedelta(minutes=window_minutes)
        )

        query = """
            SELECT
                transaction_reference,
                customer_id,
                amount,
                merchant_name,
                merchant_category,
                payment_method,
                device_type,
                transaction_time,
                location,
                ip_address,
                status
            FROM transactions
            WHERE customer_id = %s
              AND transaction_time BETWEEN %s AND %s
            ORDER BY transaction_time
        """

        connection = self._get_connection()

        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    query,
                    (
                        customer_id,
                        window_start,
                        transaction_time,
                    ),
                )
                rows = cursor.fetchall()
        finally:
            connection.close()

        transactions = []

        for row in rows:
            try:
                historical_time = row[7]

                if historical_time is None:
                    continue

                historical_time = self._normalize_datetime(
                    historical_time
                )

                amount = row[2]

                if isinstance(amount, Decimal):
                    amount = float(amount)

                transaction = Transaction(
                    customer_id=int(row[1]),
                    transaction_reference=str(row[0]),
                    amount=amount,
                    merchant_name=str(row[3]),
                    merchant_category=str(row[4]),
                    payment_method=str(row[5]),
                    device_type=str(row[6]),
                    transaction_time=historical_time,
                    location=str(row[8]),
                    ip_address=str(row[9]),
                    status=str(row[10]),
                )
            except (
                TypeError,
                ValueError,
                IndexError,
            ):
                continue

            transactions.append(transaction)

        return transactions
