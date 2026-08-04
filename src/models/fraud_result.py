from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class FraudResult:
    transaction_reference: str
    risk_score: int
    risk_level: str
    is_fraud: bool
    reasons: str
    evaluated_at: datetime

    def to_dict(self):
        data = asdict(self)

        # DynamoDB cannot store datetime objects
        data["evaluated_at"] = self.evaluated_at.isoformat()

        return data