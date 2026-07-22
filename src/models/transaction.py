from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class Transaction:
    customer_id: int
    transaction_reference: str
    amount: float
    merchant_name: str
    merchant_category: str
    payment_method: str
    device_type: str
    transaction_time: datetime
    location: str
    ip_address: str
    status: str = "APPROVED"

    def to_dict(self):
        return asdict(self)