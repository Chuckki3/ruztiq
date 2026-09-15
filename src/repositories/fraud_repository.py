import logging
from datetime import datetime

from botocore.exceptions import ClientError

from src.models.fraud_result import FraudResult
from src.services.dynamodb import FRAUD_RESULTS_TABLE

logger = logging.getLogger(__name__)


class FraudRepository:
    """
    Repository responsible for persisting fraud
    evaluation results.
    """

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
        try:
            response = FRAUD_RESULTS_TABLE.get_item(
                Key={
                    "transaction_reference": transaction_reference,
                }
            )
        except Exception:
            logger.exception(
                "Failed to retrieve fraud result: %s",
                transaction_reference,
            )
            raise

        item = response.get("Item")

        if not item:
            return None

        evaluated_at = item["evaluated_at"]

        if isinstance(evaluated_at, datetime):
            evaluated_datetime = evaluated_at
        else:
            evaluated_datetime = datetime.fromisoformat(
                str(evaluated_at)
            )

        fraud_result = FraudResult(
            transaction_reference=str(
                item["transaction_reference"]
            ),
            risk_score=int(item["risk_score"]),
            risk_level=str(item["risk_level"]),
            is_fraud=bool(item["is_fraud"]),
            reasons=str(item["reasons"]),
            evaluated_at=evaluated_datetime,
        )

        decision = {
            "decision": item.get(
                "decision",
                self._legacy_decision(fraud_result),
            ),
            "decision_reason": item.get(
                "decision_reason",
                "Existing fraud result",
            ),
            "risk_score": int(
                item.get(
                    "decision_risk_score",
                    fraud_result.risk_score,
                )
            ),
            "risk_level": item.get(
                "decision_risk_level",
                fraud_result.risk_level,
            ),
            "is_fraud": bool(
                item.get(
                    "decision_is_fraud",
                    fraud_result.is_fraud,
                )
            ),
            "velocity_violation": bool(
                item.get(
                    "velocity_violation",
                    False,
                )
            ),
        }

        return {
            "fraud_result": fraud_result,
            "decision": decision,
        }

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
        Store a fraud evaluation result in DynamoDB.

        This method preserves the original repository
        behaviour and remains available for existing callers.
        """
        item = result.to_dict()

        try:
            FRAUD_RESULTS_TABLE.put_item(
                Item=item
            )

            logger.info(
                "Fraud result stored: %s",
                result.transaction_reference,
            )

        except Exception:
            logger.exception(
                "Failed to store fraud result."
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

        The decision snapshot is persisted alongside the
        fraud result without changing the FraudResult domain
        model.

        Returns:
            True if this request created the result.
            False if another request already created it.
        """
        item = result.to_dict()

        item.update(
            {
                "decision": decision["decision"],
                "decision_reason": decision["decision_reason"],
                "decision_risk_score": decision["risk_score"],
                "decision_risk_level": decision["risk_level"],
                "decision_is_fraud": decision["is_fraud"],
                "velocity_violation": decision[
                    "velocity_violation"
                ],
            }
        )

        try:
            FRAUD_RESULTS_TABLE.put_item(
                Item=item,
                ConditionExpression=(
                    "attribute_not_exists("
                    "transaction_reference"
                    ")"
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

            if error_code == "ConditionalCheckFailedException":
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
        """
        response = FRAUD_RESULTS_TABLE.scan(
            Select="COUNT"
        )
        return response["Count"]