from datetime import datetime
from unittest.mock import MagicMock, patch

from src.services.pipeline_service import PipelineService


def make_transaction():
    transaction = MagicMock()

    transaction.transaction_reference = "TX-TEST-001"
    transaction.customer_id = 1001
    transaction.transaction_time = datetime(2026, 8, 5, 12, 0, 0)

    return transaction


def make_fraud_result():
    fraud_result = MagicMock()

    fraud_result.transaction_reference = "TX-TEST-001"
    fraud_result.risk_score = 82.5
    fraud_result.risk_level = "HIGH"
    fraud_result.is_fraud = True
    fraud_result.reasons = [
        "New device detected",
        "High transaction velocity",
    ]

    return fraud_result


@patch("src.services.pipeline_service.MetricsService")
def test_pipeline_processes_transaction_in_correct_order(
    mock_metrics,
):
    """
    Verify that the production pipeline evaluates the
    transaction using historical information before
    learning the current transaction.
    """

    pipeline = PipelineService()

    transaction = make_transaction()
    fraud_result = make_fraud_result()

    profile = MagicMock()
    updated_profile = MagicMock()

    velocity_result = {
        "is_violation": True,
        "recent_transactions": 6,
    }

    #
    # Mock customer profile
    #

    pipeline.profile_service.repository.get_or_create = (
        MagicMock(return_value=profile)
    )

    pipeline.profile_service.learn = MagicMock(
        return_value=updated_profile
    )

    #
    # Mock transaction history
    #

    historical_transactions = [
        MagicMock(),
        MagicMock(),
    ]

    pipeline.transaction_repository.get_recent_transactions = (
        MagicMock(
            return_value=historical_transactions
        )
    )

    #
    # Mock velocity engine
    #

    pipeline.velocity_engine.score = MagicMock(
        return_value=velocity_result
    )

    #
    # Mock fraud engine
    #

    pipeline.fraud_engine.evaluate = MagicMock(
        return_value=fraud_result
    )

    #
    # Mock repositories
    #

    pipeline.fraud_repository.insert_result = MagicMock()

    pipeline.transaction_repository.insert_transaction = (
        MagicMock()
    )

    #
    # Process transaction
    #

    result = pipeline.process_existing_transaction(
        transaction
    )

    #
    # Verify result
    #

    assert result["transaction"] is transaction
    assert result["profile"] is updated_profile
    assert result["velocity"] == velocity_result
    assert result["fraud_result"] is fraud_result

    #
    # Verify profile was loaded
    #

    pipeline.profile_service.repository.get_or_create.assert_called_once_with(
        1001
    )

    #
    # Verify historical transactions were retrieved
    #

    pipeline.transaction_repository.get_recent_transactions.assert_called_once_with(
        customer_id=1001,
        transaction_time=transaction.transaction_time,
        window_minutes=5,
    )

    #
    # Verify velocity analysis
    #

    pipeline.velocity_engine.score.assert_called_once_with(
        transaction_time=transaction.transaction_time,
        transaction_history=historical_transactions,
    )

    #
    # Verify fraud engine received the EXISTING profile
    #

    pipeline.fraud_engine.evaluate.assert_called_once_with(
        transaction,
        profile,
        velocity_result=velocity_result,
    )

    #
    # Verify fraud result was persisted
    #

    pipeline.fraud_repository.insert_result.assert_called_once_with(
        fraud_result
    )

    #
    # Verify current transaction was learned
    #

    pipeline.profile_service.learn.assert_called_once_with(
        transaction
    )

    #
    # Verify transaction was persisted
    #

    pipeline.transaction_repository.insert_transaction.assert_called_once_with(
        transaction
    )

    #
    # Verify metrics
    #

    mock_metrics.transaction_processed.assert_called_once_with()

    mock_metrics.fraud_score.assert_called_once_with(
        82.5
    )

    mock_metrics.fraud_detected.assert_called_once_with()


@patch("src.services.pipeline_service.MetricsService")
def test_pipeline_does_not_learn_transaction_before_fraud_evaluation(
    mock_metrics,
):
    """
    Critical regression test.

    The current transaction must not be added to the
    customer profile before FraudEngine evaluates it.
    """

    pipeline = PipelineService()

    transaction = make_transaction()
    fraud_result = make_fraud_result()

    profile = MagicMock()
    velocity_result = {
        "is_violation": False,
        "recent_transactions": 2,
    }

    pipeline.profile_service.repository.get_or_create = (
        MagicMock(return_value=profile)
    )

    pipeline.profile_service.learn = MagicMock(
        return_value=profile
    )

    pipeline.transaction_repository.get_recent_transactions = (
        MagicMock(return_value=[])
    )

    pipeline.velocity_engine.score = MagicMock(
        return_value=velocity_result
    )

    call_order = []

    def fraud_evaluate(*args, **kwargs):
        call_order.append("fraud")
        return fraud_result

    def profile_learn(*args, **kwargs):
        call_order.append("learn")
        return profile

    pipeline.fraud_engine.evaluate = MagicMock(
        side_effect=fraud_evaluate
    )

    pipeline.profile_service.learn = MagicMock(
        side_effect=profile_learn
    )

    pipeline.fraud_repository.insert_result = MagicMock()

    pipeline.transaction_repository.insert_transaction = (
        MagicMock()
    )

    pipeline.process_existing_transaction(
        transaction
    )

    assert call_order == [
        "fraud",
        "learn",
    ]


@patch("src.services.pipeline_service.MetricsService")
def test_pipeline_does_not_count_current_transaction_in_history(
    mock_metrics,
):
    """
    Verify that historical transactions are retrieved before
    the current transaction is persisted.
    """

    pipeline = PipelineService()

    transaction = make_transaction()
    fraud_result = make_fraud_result()

    profile = MagicMock()

    pipeline.profile_service.repository.get_or_create = (
        MagicMock(return_value=profile)
    )

    pipeline.profile_service.learn = MagicMock(
        return_value=profile
    )

    historical_transactions = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    pipeline.transaction_repository.get_recent_transactions = (
        MagicMock(
            return_value=historical_transactions
        )
    )

    pipeline.velocity_engine.score = MagicMock(
        return_value={
            "is_violation": False,
            "recent_transactions": 3,
        }
    )

    pipeline.fraud_engine.evaluate = MagicMock(
        return_value=fraud_result
    )

    call_order = []

    def get_history(*args, **kwargs):
        call_order.append("history")
        return historical_transactions

    def insert_transaction(*args, **kwargs):
        call_order.append("transaction_insert")

    pipeline.transaction_repository.get_recent_transactions = (
        MagicMock(
            side_effect=get_history
        )
    )

    pipeline.transaction_repository.insert_transaction = (
        MagicMock(
            side_effect=insert_transaction
        )
    )

    pipeline.fraud_repository.insert_result = MagicMock()

    pipeline.process_existing_transaction(
        transaction
    )

    assert call_order == [
        "history",
        "transaction_insert",
    ]