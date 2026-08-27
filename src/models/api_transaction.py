from dataclasses import dataclass
from datetime import datetime, timezone

from src.models.transaction import Transaction


@dataclass(slots=True)
class APITransaction:
    """
    Represents an incoming transaction received through the API.

    This model represents the external API contract and converts
    the incoming payload into the internal Transaction model.
    """

    transaction_reference: str
    customer_id: int
    amount: float
    merchant_name: str
    merchant_category: str
    payment_method: str
    device_type: str
    location: str
    ip_address: str
    status: str = "APPROVED"

    # External API fields that are currently accepted but are not
    # yet represented in the internal Transaction model.
    currency: str | None = None
    merchant_id: str | None = None
    device_id: str | None = None
    transaction_time: str | None = None

    def to_transaction(self) -> Transaction:
        """
        Convert the API transaction into the internal Transaction model.
        """

        if self.transaction_time:
            transaction_time = datetime.fromisoformat(
                self.transaction_time
            )

            if transaction_time.tzinfo is None:
                transaction_time = transaction_time.replace(
                    tzinfo=timezone.utc
                )
        else:
            transaction_time = datetime.now(timezone.utc)

        return Transaction(
            customer_id=self.customer_id,
            transaction_reference=self.transaction_reference,
            amount=self.amount,
            merchant_name=self.merchant_name,
            merchant_category=self.merchant_category,
            payment_method=self.payment_method.upper(),
            device_type=self.device_type,
            transaction_time=transaction_time,
            location=self.location,
            ip_address=self.ip_address,
            status=self.status.upper(),
        )