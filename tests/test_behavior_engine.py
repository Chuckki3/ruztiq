from datetime import datetime

from src.behaviour.behaviour_engine import BehaviorEngine
from src.models.customer_profile import CustomerProfile


def make_profile():

    return CustomerProfile(
        customer_id=1,
        first_seen=datetime.utcnow(),
        last_seen=datetime.utcnow(),
        total_transactions=20,
        total_amount=200000,
        average_amount=10000,
        highest_amount=25000,
        lowest_amount=1000,
        failed_transactions=1,
        successful_transactions=19,
        known_devices=[
            "iPhone",
        ],
        known_locations=[
            "Lagos",
        ],
        known_payment_methods=[
            "CARD",
        ],
        known_merchants=[
            "Amazon",
        ],
        known_ips=[
            "102.89.45.1",
        ],
        recent_transactions=[
            "TX-001",
        ],
    )


def make_transaction(
    device_type="iPhone",
    location="Lagos",
    payment_method="CARD",
    merchant_name="Amazon",
    ip_address="102.89.45.1",
    amount=5000,
):

    class Transaction:
        pass

    transaction = Transaction()

    transaction.customer_id = 1

    transaction.transaction_reference = (
        "TEST-BEHAVIOUR"
    )

    transaction.device_type = device_type
    transaction.location = location
    transaction.payment_method = payment_method
    transaction.merchant_name = merchant_name
    transaction.ip_address = ip_address
    transaction.amount = amount
    transaction.transaction_time = datetime.utcnow()
    transaction.status = "APPROVED"

    return transaction


def test_normal_customer_behavior():

    profile = make_profile()
    transaction = make_transaction()

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert result["signals"] == []
    assert result["signal_count"] == 0
    assert result["is_anomalous"] is False


def test_new_device():

    profile = make_profile()

    transaction = make_transaction(
        device_type="Android",
    )

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert "NEW_DEVICE" in result["signals"]


def test_new_ip():

    profile = make_profile()

    transaction = make_transaction(
        ip_address="197.210.54.20",
    )

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert "NEW_IP" in result["signals"]


def test_new_location():

    profile = make_profile()

    transaction = make_transaction(
        location="Abuja",
    )

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert "NEW_LOCATION" in result["signals"]


def test_new_merchant():

    profile = make_profile()

    transaction = make_transaction(
        merchant_name="Unknown Merchant",
    )

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert "NEW_MERCHANT" in result["signals"]


def test_new_payment_method():

    profile = make_profile()

    transaction = make_transaction(
        payment_method="USSD",
    )

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert "NEW_PAYMENT_METHOD" in result["signals"]


def test_amount_anomaly():

    profile = make_profile()

    transaction = make_transaction(
        amount=60000,
    )

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert "AMOUNT_ANOMALY" in result["signals"]


def test_multiple_failed_attempts():

    profile = make_profile()

    profile.failed_transactions = 5

    transaction = make_transaction()

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert (
        "MULTIPLE_FAILED_ATTEMPTS"
        in result["signals"]
    )


def test_multiple_behavioral_signals():

    profile = make_profile()

    transaction = make_transaction(
        device_type="Android",
        location="Abuja",
        payment_method="USSD",
        merchant_name="Unknown Merchant",
        ip_address="197.210.54.20",
        amount=100000,
    )

    engine = BehaviorEngine()

    result = engine.analyze(
        transaction,
        profile,
    )

    assert "NEW_DEVICE" in result["signals"]
    assert "NEW_LOCATION" in result["signals"]
    assert "NEW_PAYMENT_METHOD" in result["signals"]
    assert "NEW_MERCHANT" in result["signals"]
    assert "NEW_IP" in result["signals"]
    assert "AMOUNT_ANOMALY" in result["signals"]

    assert result["signal_count"] >= 6
    assert result["is_anomalous"] is True
