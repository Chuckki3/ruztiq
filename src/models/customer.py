from dataclasses import dataclass, asdict


@dataclass
class Customer:
    first_name: str
    last_name: str
    email: str
    phone: str
    state: str
    account_age_days: int
    device_preference: str

    def to_dict(self):
        return asdict(self)