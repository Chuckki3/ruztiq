from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class FraudResult:
    transaction_id: int
    risk_score: int
    risk_level: str
    is_fraud: bool
    reasons: str
    evaluated_at: datetime

    def to_dict(self):
        return asdict(self)