import json
import logging
import os
from datetime import datetime

import boto3
import psycopg2


logger = logging.getLogger(__name__)


class AnalyticsRepository:
    """
    PostgreSQL persistence boundary for fraud analytics results.

    This class owns PostgreSQL-specific concerns so that callers do not
    need to know how analytics results are persisted.
    """

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

    def save_fraud_result(
        self,
        transaction_reference,
        risk_score,
        risk_level,
        is_fraud,
        reasons,
        evaluated_at,
    ):
        """
        Persist a fraud result into the PostgreSQL analytics table.

        Existing transaction references are updated so that MODIFY events
        remain idempotent.
        """
        connection = self.get_postgres_connection()

        try:
            with connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO fraud_results_analytics (
                            transaction_reference,
                            risk_score,
                            risk_level,
                            is_fraud,
                            reasons,
                            evaluated_at
                        )
                        VALUES (%s, %s, %s, %s, %s, %s)
                        ON CONFLICT (transaction_reference)
                        DO UPDATE SET
                            risk_score = EXCLUDED.risk_score,
                            risk_level = EXCLUDED.risk_level,
                            is_fraud = EXCLUDED.is_fraud,
                            reasons = EXCLUDED.reasons,
                            evaluated_at = EXCLUDED.evaluated_at,
                            synced_at = CURRENT_TIMESTAMP
                        """,
                        (
                            transaction_reference,
                            risk_score,
                            risk_level,
                            is_fraud,
                            reasons,
                            evaluated_at,
                        ),
                    )

            logger.info(
                "Successfully synchronized fraud result: %s",
                transaction_reference,
            )

        finally:
            connection.close()