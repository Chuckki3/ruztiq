from dataclasses import dataclass, asdict


@dataclass
class FraudResult:
    transaction_id: int
    risk_score: int
    is_fraud: bool
    triggered_rules: str

    def to_dict(self):
        return asdict(self)