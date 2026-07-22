import random
import uuid
from datetime import datetime

from faker import Faker

from src.models.transaction import Transaction
from src.utils.constants import (
    MERCHANTS,
    PAYMENT_METHODS,
    NIGERIAN_STATES,
    DEVICE_TYPES,
)

fake = Faker("en_NG")


def generate_transaction(customer_id: int) -> Transaction:
    """
    Generate a realistic transaction for an existing customer.
    """

    merchant = random.choice(MERCHANTS)

    amount = round(
        random.uniform(
            merchant["min_amount"],
            merchant["max_amount"],
        ),
        2,
    )

    return Transaction(
        customer_id=customer_id,
        transaction_reference=f"TXN-{uuid.uuid4().hex[:12].upper()}",
        amount=amount,
        merchant_name=merchant["name"],
        merchant_category=merchant["category"],
        payment_method=random.choice(PAYMENT_METHODS),
        device_type=random.choice(DEVICE_TYPES),
        transaction_time=datetime.now(),
        location=random.choice(NIGERIAN_STATES),
        ip_address=fake.ipv4_public(),
        status="APPROVED",
    )


if __name__ == "__main__":
    transaction = generate_transaction(1)
    print(transaction)