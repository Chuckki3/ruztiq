from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Transaction:
    """
    Represents a financial transaction processed by RuztIQ.
    """

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

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the transaction into a dictionary suitable for storage.
        """

        data = asdict(self)

        data["transaction_time"] = (
            self.transaction_time.isoformat()
        )

        return data