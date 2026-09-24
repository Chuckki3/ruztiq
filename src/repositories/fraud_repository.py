import logging
import os
from datetime import UTC, datetime
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError

from src.models.fraud_result import FraudResult


logger = logging.getLogger(__name__)


class FraudRepository:
    """
    DynamoDB persistence boundary for fraud evaluation results.

    Fraud results are stored in the FraudResults table with
    transaction_reference as the partition key.

    The repository translates between DynamoDB items and the
    FraudResult domain model while preserving persisted decision
    snapshots and legacy-result compatibility.
    """

    def __init__(self):
        self.region_name = os.getenv(
            "AWS_REGION_NAME",
            "eu-west-1",
        )
        self.table_name = os.getenv(
            "FRAUD_RESULTS_TABLE",
            "FraudResults",
        )

        self.dynamodb = boto3.resource(
            "dynamodb",
            region_name=self.region_name,
        )
        self.table = self.dynamodb.Table(
            self.table_name
        )

    @staticmethod
    def _normalize_datetime(value):
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=UTC)

        return value.astimezone(UTC)

    @classmethod
    def _datetime_to_string(cls, value):
        normalized = cls._normalize_datetime(value)

        if normalized is None:
            return None

        return normalized.isoformat()

    @classmethod
    def _string_to_datetime(cls, value):
        if value is None:
            return None

        if isinstance(value, datetime):
            return cls._normalize_datetime(value)

        parsed = datetime.fromisoformat(
            str(value)
        )

        return cls._normalize_datetime(parsed)

    @staticmethod
    def _item_to_fraud_result(item):
        if item is None:
            return None

        evaluated_at = item.get("evaluated_at")

        return FraudResult(
            transaction_reference=str(
                item["transaction_reference"]
            ),
            risk_score=int(
                item.get("risk_score", 0)
            ),
            risk_level=str(
                item.get("risk_level", "")
            ),
            is_fraud=bool(
                item.get("is_fraud", False)
            ),
            reasons=str(
                item.get("reasons", "")
            ),
            evaluated_at=(
                FraudRepository._string_to_datetime(
                    evaluated_at
                )
            ),
        )

    @classmethod
    def _result_item(
        cls,
        result: FraudResult,
    ):
        return {
            "transaction_reference": str(
                result.transaction_reference
            ),
            "risk_score": int(
                result.risk_score
            ),
            "risk_level": str(
                result.risk_level
            ),
            "is_fraud": bool(
                result.is_fraud
            ),
            "reasons": str(
                result.reasons
            ),
            "evaluated_at": cls._datetime_to_string(
                result.evaluated_at
            ),
        }

    @classmethod
    def _result_with_decision_item(
        cls,
        result: FraudResult,
        decision: dict,
    ):
        item = cls._result_item(result)

        item.update(
            {
                "decision": str(
                    decision["decision"]
                ),
                "decision_reason": str(
                    decision["decision_reason"]
                ),
                "decision_risk_score": int(
                    decision["risk_score"]
                ),
                "decision_risk_level": str(
                    decision["risk_level"]
                ),
                "decision_is_fraud": bool(
                    decision["is_fraud"]
                ),
                "velocity_violation": bool(
                    decision["velocity_violation"]
                ),
            }
        )

        return item

    @staticmethod
    def _legacy_decision(
        fraud_result: FraudResult,
    ) -> str:
        """
        Provide a conservative decision for fraud results
        created before decision snapshots were persisted.
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

    @staticmethod
    def _decision_snapshot(
        item,
        fraud_result: FraudResult,
    ):
        decision = item.get("decision")

        if decision is None:
            persisted_decision = (
                FraudRepository._legacy_decision(
                    fraud_result
                )
            )
        else:
            persisted_decision = str(decision)

        decision_reason = item.get(
            "decision_reason"
        )

        decision_risk_score = item.get(
            "decision_risk_score"
        )

        decision_risk_level = item.get(
            "decision_risk_level"
        )

        decision_is_fraud = item.get(
            "decision_is_fraud"
        )

        velocity_violation = item.get(
            "velocity_violation"
        )

        return {
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

    def get_result(
        self,
        transaction_reference: str,
    ) -> dict | None:
        """
        Retrieve an existing fraud evaluation and its
        persisted decision snapshot.

        Returns None when no result exists.

        Legacy records without decision fields are supported
        by reconstructing the decision from the FraudResult.
        """
        try:
            response = self.table.get_item(
                Key={
                    "transaction_reference": str(
                        transaction_reference
                    )
                }
            )

            item = response.get("Item")

            if item is None:
                return None

            fraud_result = self._item_to_fraud_result(
                item
            )

            return {
                "fraud_result": fraud_result,
                "decision": self._decision_snapshot(
                    item,
                    fraud_result,
                ),
            }

        except Exception:
            logger.exception(
                "Failed to retrieve fraud result: %s",
                transaction_reference,
            )
            raise

    def insert_result(
        self,
        result: FraudResult,
    ) -> None:
        """
        Store a fraud evaluation result.

        This method preserves the original public repository
        interface and performs a normal DynamoDB put.
        """
        try:
            self.table.put_item(
                Item=self._result_item(result)
            )

            logger.info(
                "Fraud result stored: %s",
                result.transaction_reference,
            )

        except Exception:
            logger.exception(
                "Failed to store fraud result: %s",
                result.transaction_reference,
            )
            raise

    def insert_result_if_absent(
        self,
        result: FraudResult,
        decision: dict,
    ) -> bool:
        """
        Atomically store a fraud result only when its
        transaction reference does not already exist.

        Returns:
            True if this request created the result.
            False if another request already created it.
        """
        item = self._result_with_decision_item(
            result,
            decision,
        )

        try:
            self.table.put_item(
                Item=item,
                ConditionExpression=(
                    "attribute_not_exists("
                    "transaction_reference)"
                ),
            )

            logger.info(
                "Fraud result atomically stored: %s",
                result.transaction_reference,
            )

            return True

        except ClientError as exc:
            error_code = exc.response.get(
                "Error",
                {},
            ).get("Code")

            if (
                error_code
                == "ConditionalCheckFailedException"
            ):
                logger.info(
                    "Fraud result already exists: %s",
                    result.transaction_reference,
                )

                return False

            logger.exception(
                "Failed to atomically store fraud result: %s",
                result.transaction_reference,
            )
            raise

        except Exception:
            logger.exception(
                "Failed to atomically store fraud result: %s",
                result.transaction_reference,
            )
            raise

    def count_results(self) -> int:
        """
        Return the number of fraud evaluations stored.

        DynamoDB scans are paginated, so all pages are counted.
        """
        total = 0
        scan_kwargs = {}

        while True:
            response = self.table.scan(
                **scan_kwargs
            )

            total += int(
                response.get("Count", 0)
            )

            last_evaluated_key = response.get(
                "LastEvaluatedKey"
            )

            if not last_evaluated_key:
                break

            scan_kwargs = {
                "ExclusiveStartKey":
                    last_evaluated_key
            }

        return total
