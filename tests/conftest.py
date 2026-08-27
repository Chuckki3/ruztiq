import os
from datetime import datetime, UTC

import pytest

#
# Fake Lambda environment variables
#

os.environ.setdefault(
    "TRANSACTIONS_TABLE",
    "Transactions",
)

os.environ.setdefault(
    "FRAUD_RESULTS_TABLE",
    "FraudResults",
)

from src.models.transaction import Transaction


@pytest.fixture
def sample_transaction():

    return Transaction(
        customer_id=1,
        transaction_reference="TEST-123456",
        amount=250000,
        merchant_name="Amazon",
        merchant_category="Shopping",
        payment_method="CARD",
        device_type="Mobile",
        transaction_time=datetime(
            2026,
            8,
            27,
            12,
            0,
            0,
            tzinfo=UTC,
        ),
        location="Lagos",
        ip_address="102.89.45.1",
        status="APPROVED",
    )


@pytest.fixture
def suspicious_transaction():

    return Transaction(
        customer_id=1,
        transaction_reference="TEST-FRAUD",
        amount=300000,
        merchant_name="Casino Royale",
        merchant_category="Entertainment",
        payment_method="USSD",
        device_type="Mobile",
        transaction_time=datetime(
            2026,
            8,
            27,
            2,
            0,
            0,
            tzinfo=UTC,
        ),
        location="Lagos",
        ip_address="102.89.45.1",
        status="FAILED",
    )