from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class Customer:
    """
    Represents a customer profile used for synthetic transaction generation.
    """

    first_name: str
    last_name: str
    email: str
    phone: str
    state: str
    account_age_days: int
    device_preference: str

    def to_dict(self) -> dict[str, Any]:
        """
        Convert the customer into a dictionary.
        """

        return asdict(self)