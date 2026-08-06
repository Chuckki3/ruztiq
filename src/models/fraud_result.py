from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class FraudResult:
    """
    Represents the fraud evaluation result for a transaction.
    """

    transaction_reference: str
    risk_score: int
    risk_level: str
    is_fraud: bool
    reasons: str
    evaluated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the fraud result into a dictionary suitable for DynamoDB.
        """

        data = asdict(self)

        data["evaluated_at"] = (
            self.evaluated_at.isoformat()
        )

        return data