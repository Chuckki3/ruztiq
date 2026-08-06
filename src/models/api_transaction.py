import uuid
from dataclasses import dataclass
from datetime import datetime

from src.models.transaction import Transaction


@dataclass(slots=True)
class APITransaction:
    """
    Represents an incoming transaction received through the API.
    """

    customer_id: int
    amount: float
    merchant_name: str
    merchant_category: str
    payment_method: str
    device_type: str
    location: str
    ip_address: str
    status: str = "APPROVED"

    def to_transaction(self) -> Transaction:
        """
        Convert an API payload into an internal Transaction object.
        """

        return Transaction(
            customer_id=self.customer_id,
            transaction_reference=(
                f"API-{uuid.uuid4().hex[:12].upper()}"
            ),
            amount=self.amount,
            merchant_name=self.merchant_name,
            merchant_category=self.merchant_category,
            payment_method=self.payment_method,
            device_type=self.device_type,
            transaction_time=datetime.utcnow(),
            location=self.location,
            ip_address=self.ip_address,
            status=self.status,
        )