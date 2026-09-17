import json
import logging
import os
from datetime import datetime

import boto3
import psycopg2

from src.models.fraud_result import FraudResult

logger = logging.getLogger(__name__)


class FraudRepository:
    """
    PostgreSQL-backed repository responsible for persisting
    fraud evaluation results.
    """

    def __init__(self):
        self.db_secret_name = os.getenv(
            "DB_SECRET_NAME",
            "sentineliq/rds/postgres",
        )
        self.db_host = os.getenv("DB_HOST")
        self.db_port = int(
            os.getenv("DB_PORT", "5432")
        )
        self.db_name = os.getenv("DB_NAME")

        self.secrets_client = boto3.client(
            "secretsmanager"
        )

    def _get_database_credentials(self):
        response = self.secrets_client.get_secret_value(
            SecretId=self.db_secret_name
        )

        secret_string = response.get("SecretString")
        if not secret_string:
            raise ValueError(
                "Database secret does not contain SecretString"
            )

        secret = json.loads(secret_string)

        username = secret.get("username")
        password = secret.get("password")

        if not username or not password:
            raise ValueError(
                "Database secret must contain username and password"
            )

        return username, password

    def _get_connection(self):
        username, password = (
            self._get_database_credentials()
        )

        return psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            dbname=self.db_name,
            user=username,
            password=password,
            connect_timeout=10,
        )

    def get_result(
        self,
        transaction_reference: str,
    ) -> dict | None:
        """
        Retrieve an existing fraud evaluation and its
        persisted decision snapshot.

        Returns:
            A dictionary containing:
                fraud_result: FraudResult
                decision: persisted decision dictionary

            None if no result exists.

        Legacy fraud results created before decision
        persistence are supported. In that case the decision
        dictionary is reconstructed from the stored fraud
        result with velocity_violation=False.
        """
        connection = None
        cursor = None

        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT
                    transaction_reference,
                    risk_score,
                    risk_level,
                    is_fraud,
                    reasons,
                    evaluated_at,
                    decision,
                    decision_reason,
                    decision_risk_score,
                    decision_risk_level,
                    decision_is_fraud,
                    velocity_violation
                FROM fraud_results
                WHERE transaction_reference = %s
                """,
                (transaction_reference,),
            )

            row = cursor.fetchone()

            if row is None:
                return None

            (
                stored_reference,
                risk_score,
                risk_level,
                is_fraud,
                reasons,
                evaluated_at,
                decision,
                decision_reason,
                decision_risk_score,
                decision_risk_level,
                decision_is_fraud,
                velocity_violation,
            ) = row

            fraud_result = FraudResult(
                transaction_reference=str(
                    stored_reference
                ),
                risk_score=int(risk_score),
                risk_level=str(risk_level),
                is_fraud=bool(is_fraud),
                reasons=str(reasons),
                evaluated_at=evaluated_at,
            )

            if decision is None:
                persisted_decision = (
                    self._legacy_decision(fraud_result)
                )
            else:
                persisted_decision = str(decision)

            decision_snapshot = {
                "decision": persisted_decision,
                "decision_reason": (
                    str(decision_reason)
                    if decision_reason is not None
                    else "Existing fraud result"
                ),
                "risk_score": int(
                    decision_risk_score
                    if decision_risk_score is not None
                    else fraud_result.risk_score
                ),
                "risk_level": (
                    str(decision_risk_level)
                    if decision_risk_level is not None
                    else fraud_result.risk_level
                ),
                "is_fraud": bool(
                    decision_is_fraud
                    if decision_is_fraud is not None
                    else fraud_result.is_fraud
                ),
                "velocity_violation": bool(
                    velocity_violation
                    if velocity_violation is not None
                    else False
                ),
            }

            return {
                "fraud_result": fraud_result,
                "decision": decision_snapshot,
            }

        except Exception:
            logger.exception(
                "Failed to retrieve fraud result: %s",
                transaction_reference,
            )
            raise

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    @staticmethod
    def _legacy_decision(
        fraud_result: FraudResult,
    ) -> str:
        """
        Provide a conservative decision for fraud results
        created before decision snapshots were persisted.

        This is only used for legacy records.
        """
        if fraud_result.risk_score >= 80:
            return "DECLINE"

        if (
            fraud_result.is_fraud
            and fraud_result.risk_score >= 40
        ):
            return "DECLINE"

        if fraud_result.risk_score >= 40:
            return "REVIEW"

        return "APPROVE"

    def insert_result(
        self,
        result: FraudResult,
    ) -> None:
        """
        Store a fraud evaluation result in PostgreSQL.

        This method preserves the original repository
        behaviour and remains available for existing callers.
        """
        connection = None
        cursor = None

        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO fraud_results (
                    transaction_reference,
                    risk_score,
                    risk_level,
                    is_fraud,
                    reasons,
                    evaluated_at
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    result.transaction_reference,
                    result.risk_score,
                    result.risk_level,
                    result.is_fraud,
                    result.reasons,
                    result.evaluated_at,
                ),
            )

            connection.commit()

            logger.info(
                "Fraud result stored: %s",
                result.transaction_reference,
            )

        except Exception:
            if connection is not None:
                connection.rollback()

            logger.exception(
                "Failed to store fraud result: %s",
                result.transaction_reference,
            )
            raise

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def insert_result_if_absent(
        self,
        result: FraudResult,
        decision: dict,
    ) -> bool:
        """
        Atomically store a fraud result only when its
        transaction reference does not already exist.

        The decision snapshot is persisted alongside the
        fraud result without changing the FraudResult domain
        model.

        Returns:
            True if this request created the result.
            False if another request already created it.
        """
        connection = None
        cursor = None

        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                INSERT INTO fraud_results (
                    transaction_reference,
                    risk_score,
                    risk_level,
                    is_fraud,
                    reasons,
                    evaluated_at,
                    decision,
                    decision_reason,
                    decision_risk_score,
                    decision_risk_level,
                    decision_is_fraud,
                    velocity_violation
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (
                    transaction_reference
                ) DO NOTHING
                RETURNING transaction_reference
                """,
                (
                    result.transaction_reference,
                    result.risk_score,
                    result.risk_level,
                    result.is_fraud,
                    result.reasons,
                    result.evaluated_at,
                    decision["decision"],
                    decision["decision_reason"],
                    decision["risk_score"],
                    decision["risk_level"],
                    decision["is_fraud"],
                    decision["velocity_violation"],
                ),
            )

            inserted_row = cursor.fetchone()
            connection.commit()

            if inserted_row is None:
                logger.info(
                    "Fraud result already exists: %s",
                    result.transaction_reference,
                )
                return False

            logger.info(
                "Fraud result atomically stored: %s",
                result.transaction_reference,
            )
            return True

        except Exception:
            if connection is not None:
                connection.rollback()

            logger.exception(
                "Failed to atomically store fraud result: %s",
                result.transaction_reference,
            )
            raise

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()

    def count_results(self) -> int:
        """
        Return the number of fraud evaluations stored.
        """
        connection = None
        cursor = None

        try:
            connection = self._get_connection()
            cursor = connection.cursor()

            cursor.execute(
                """
                SELECT COUNT(*)
                FROM fraud_results
                """
            )

            row = cursor.fetchone()
            return int(row[0])

        finally:
            if cursor is not None:
                cursor.close()
            if connection is not None:
                connection.close()
