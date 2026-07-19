import random

from faker import Faker

from src.models.customer import Customer
from src.utils.constants import DEVICE_TYPES, NIGERIAN_STATES

fake = Faker("en_NG")


def generate_phone_number():
    """Generate a realistic Nigerian phone number."""
    prefixes = [
        "070",
        "080",
        "081",
        "090",
        "091"
    ]

    return random.choice(prefixes) + "".join(
        random.choices("0123456789", k=8)
    )


def generate_email(first_name: str, last_name: str):
    """Generate a realistic email address."""

    domains = [
        "gmail.com",
        "yahoo.com",
        "outlook.com"
    ]

    return (
        f"{first_name.lower()}."
        f"{last_name.lower()}"
        f"{random.randint(100,999)}"
        f"@{random.choice(domains)}"
    )


def generate_customer() -> Customer:
    """Generate a synthetic customer."""

    first_name = fake.first_name()
    last_name = fake.last_name()

    return Customer(
        first_name=first_name,
        last_name=last_name,
        email=generate_email(first_name, last_name),
        phone=generate_phone_number(),
        state=random.choice(NIGERIAN_STATES),
        account_age_days=random.randint(30, 3650),
        device_preference=random.choice(DEVICE_TYPES),
    )


if __name__ == "__main__":
    customer = generate_customer()
    print(customer)