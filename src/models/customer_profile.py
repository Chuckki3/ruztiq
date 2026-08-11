from dataclasses import dataclass, asdict, field
from datetime import datetime
from typing import List, Optional


@dataclass
class CustomerProfile:
    """
    Persistent behavioural profile for a SentinelIQ customer.

    The profile learns progressively from transactions and provides
    the historical context required for behavioural fraud detection.
    """

    customer_id: int

    first_seen: Optional[datetime] = None
    last_seen: Optional[datetime] = None

    total_transactions: int = 0

    total_amount: float = 0.0
    average_amount: float = 0.0

    highest_amount: float = 0.0
    lowest_amount: float = 0.0

    failed_transactions: int = 0
    successful_transactions: int = 0

    known_devices: List[str] = field(default_factory=list)
    known_locations: List[str] = field(default_factory=list)
    known_payment_methods: List[str] = field(default_factory=list)
    known_merchants: List[str] = field(default_factory=list)
    known_ips: List[str] = field(default_factory=list)

    recent_transactions: List[str] = field(
        default_factory=list
    )

    def to_dict(self):
        """
        Convert profile into a DynamoDB-compatible dictionary.
        """

        data = asdict(self)

        if self.first_seen is not None:
            data["first_seen"] = self.first_seen.isoformat()

        if self.last_seen is not None:
            data["last_seen"] = self.last_seen.isoformat()

        return data