from unittest.mock import MagicMock

from src.services.fraud_state_service import FraudStateService


def test_get_customer_profile_delegates_to_profile_service():
    profile = MagicMock()
    profile_service = MagicMock()
    profile_service.get_or_create = MagicMock(
        return_value=profile
    )
    transaction_repository = MagicMock()

    state_service = FraudStateService(
        profile_service=profile_service,
        transaction_repository=transaction_repository,
    )

    result = state_service.get_customer_profile(1001)

    assert result is profile
    profile_service.get_or_create.assert_called_once_with(1001)


def test_get_recent_transactions_delegates_to_transaction_repository():
    transactions = [MagicMock()]
    profile_service = MagicMock()
    transaction_repository = MagicMock()
    transaction_repository.get_recent_transactions = MagicMock(
        return_value=transactions
    )

    state_service = FraudStateService(
        profile_service=profile_service,
        transaction_repository=transaction_repository,
    )

    transaction_time = MagicMock()

    result = state_service.get_recent_transactions(
        customer_id=1001,
        transaction_time=transaction_time,
        window_minutes=5,
    )

    assert result is transactions
    transaction_repository.get_recent_transactions.assert_called_once_with(
        customer_id=1001,
        transaction_time=transaction_time,
        window_minutes=5,
    )


def test_learn_from_transaction_delegates_to_profile_service():
    transaction = MagicMock()
    profile = MagicMock()
    profile_service = MagicMock()
    profile_service.learn = MagicMock(
        return_value=profile
    )
    transaction_repository = MagicMock()

    state_service = FraudStateService(
        profile_service=profile_service,
        transaction_repository=transaction_repository,
    )

    result = state_service.learn_from_transaction(
        transaction
    )

    assert result is profile
    profile_service.learn.assert_called_once_with(
        transaction
    )


def test_persist_transaction_delegates_to_transaction_repository():
    transaction = MagicMock()
    transaction_reference = "TX-001"
    profile_service = MagicMock()
    transaction_repository = MagicMock()
    transaction_repository.insert_transaction = MagicMock(
        return_value=transaction_reference
    )

    state_service = FraudStateService(
        profile_service=profile_service,
        transaction_repository=transaction_repository,
    )

    result = state_service.persist_transaction(
        transaction
    )

    assert result == transaction_reference
    transaction_repository.insert_transaction.assert_called_once_with(
        transaction
    )


def test_get_random_customer_id_delegates_to_transaction_repository():
    profile_service = MagicMock()
    transaction_repository = MagicMock()
    transaction_repository.get_random_customer_id = MagicMock(
        return_value=1001
    )

    state_service = FraudStateService(
        profile_service=profile_service,
        transaction_repository=transaction_repository,
    )

    result = state_service.get_random_customer_id()

    assert result == 1001
    transaction_repository.get_random_customer_id.assert_called_once_with()