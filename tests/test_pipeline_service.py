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


def make_decision():
    return {
        "decision": "DECLINE",
        "decision_reason": "Risk score exceeds the automatic decline threshold.",
        "risk_score": 82,
        "risk_level": "HIGH",
        "is_fraud": True,
        "velocity_violation": True,
    }


def test_pipeline_processes_transaction_in_correct_order():
    pipeline = PipelineService()

    transaction = make_transaction()
    profile = MagicMock()
    recent_transactions = []
    velocity_result = MagicMock()
    fraud_result = make_fraud_result()
    decision = make_decision()

    pipeline.fraud_state_service.get_customer_profile = MagicMock(
        return_value=profile
    )
    pipeline.fraud_state_service.get_recent_transactions = MagicMock(
        return_value=recent_transactions
    )
    pipeline.fraud_state_service.learn_from_transaction = MagicMock()
    pipeline.fraud_state_service.persist_transaction = MagicMock()

    pipeline.fraud_repository.get_result = MagicMock(
        return_value=None
    )
    pipeline.fraud_repository.insert_result_if_absent = MagicMock(
        return_value=True
    )

    with patch.object(
        pipeline.velocity_engine,
        "score",
        return_value=velocity_result,
    ) as velocity_mock, patch.object(
        pipeline.fraud_engine,
        "evaluate",
        return_value=fraud_result,
    ) as fraud_mock, patch.object(
        pipeline,
        "determine_decision",
        return_value=decision,
    ) as decision_mock:
        result = pipeline.process_existing_transaction(transaction)

    pipeline.fraud_state_service.get_customer_profile.assert_called_once_with(
        transaction.customer_id
    )

    pipeline.fraud_state_service.get_recent_transactions.assert_called_once_with(
        customer_id=transaction.customer_id,
        transaction_time=transaction.transaction_time,
        window_minutes=pipeline.velocity_engine.window_minutes,
    )

    velocity_mock.assert_called_once_with(
        transaction_time=transaction.transaction_time,
        transaction_history=recent_transactions,
    )

    fraud_mock.assert_called_once_with(
        transaction,
        profile,
        velocity_result=velocity_result,
    )

    decision_mock.assert_called_once_with(
        fraud_result=fraud_result,
        velocity_result=velocity_result,
    )

    pipeline.fraud_repository.insert_result_if_absent.assert_called_once_with(
        result=fraud_result,
        decision=decision,
    )

    pipeline.fraud_state_service.learn_from_transaction.assert_called_once_with(
        transaction
    )

    pipeline.fraud_state_service.persist_transaction.assert_called_once_with(
        transaction
    )

    assert result["fraud_result"] is fraud_result
    assert result["decision"] == decision


def test_pipeline_does_not_learn_transaction_before_fraud_evaluation():
    pipeline = PipelineService()

    transaction = make_transaction()
    profile = MagicMock()
    velocity_result = MagicMock()
    fraud_result = make_fraud_result()
    decision = make_decision()

    pipeline.fraud_state_service.get_customer_profile = MagicMock(
        return_value=profile
    )
    pipeline.fraud_state_service.get_recent_transactions = MagicMock(
        return_value=[]
    )
    pipeline.fraud_state_service.learn_from_transaction = MagicMock()
    pipeline.fraud_state_service.persist_transaction = MagicMock()

    pipeline.fraud_repository.get_result = MagicMock(
        return_value=None
    )
    pipeline.fraud_repository.insert_result_if_absent = MagicMock(
        return_value=True
    )

    call_order = []

    def evaluate_fraud(*args, **kwargs):
        call_order.append("fraud")
        return fraud_result

    def learn_transaction(*args, **kwargs):
        call_order.append("learn")

    with patch.object(
        pipeline.velocity_engine,
        "score",
        return_value=velocity_result,
    ), patch.object(
        pipeline.fraud_engine,
        "evaluate",
        side_effect=evaluate_fraud,
    ), patch.object(
        pipeline,
        "determine_decision",
        return_value=decision,
    ):
        pipeline.fraud_state_service.learn_from_transaction.side_effect = (
            learn_transaction
        )

        pipeline.process_existing_transaction(transaction)

    assert call_order == ["fraud", "learn"]


def test_pipeline_does_not_count_current_transaction_in_history():
    pipeline = PipelineService()

    transaction = make_transaction()
    profile = MagicMock()
    velocity_result = MagicMock()
    fraud_result = make_fraud_result()
    decision = make_decision()

    historical_transaction = MagicMock()
    historical_transaction.transaction_reference = "TX-HISTORICAL-001"

    pipeline.fraud_state_service.get_customer_profile = MagicMock(
        return_value=profile
    )
    pipeline.fraud_state_service.get_recent_transactions = MagicMock(
        return_value=[historical_transaction]
    )
    pipeline.fraud_state_service.learn_from_transaction = MagicMock()
    pipeline.fraud_state_service.persist_transaction = MagicMock()

    pipeline.fraud_repository.get_result = MagicMock(
        return_value=None
    )
    pipeline.fraud_repository.insert_result_if_absent = MagicMock(
        return_value=True
    )

    with patch.object(
        pipeline.velocity_engine,
        "score",
        return_value=velocity_result,
    ), patch.object(
        pipeline.fraud_engine,
        "evaluate",
        return_value=fraud_result,
    ) as fraud_mock, patch.object(
        pipeline,
        "determine_decision",
        return_value=decision,
    ):
        pipeline.process_existing_transaction(transaction)

    fraud_mock.assert_called_once_with(
        transaction,
        profile,
        velocity_result=velocity_result,
    )


def test_duplicate_transaction_returns_existing_result_without_reprocessing():
    pipeline = PipelineService()

    transaction = make_transaction()

    existing_result = MagicMock()
    existing_result.transaction_reference = (
        transaction.transaction_reference
    )

    existing_decision = {
        "decision": "DECLINE",
        "decision_reason": "Risk score exceeds the automatic decline threshold.",
        "risk_score": 82,
        "risk_level": "HIGH",
        "is_fraud": True,
        "velocity_violation": True,
    }

    pipeline.fraud_repository.get_result = MagicMock(
        return_value={
            "fraud_result": existing_result,
            "decision": existing_decision,
        }
    )

    pipeline.fraud_state_service.get_customer_profile = MagicMock()
    pipeline.fraud_state_service.get_recent_transactions = MagicMock()
    pipeline.fraud_state_service.learn_from_transaction = MagicMock()
    pipeline.fraud_state_service.persist_transaction = MagicMock()

    with patch.object(
        pipeline.fraud_engine,
        "evaluate",
    ) as fraud_mock, patch.object(
        pipeline.velocity_engine,
        "score",
    ) as velocity_mock, patch.object(
        pipeline,
        "determine_decision",
    ) as decision_mock:
        result = pipeline.process_existing_transaction(transaction)

    assert result["fraud_result"] is existing_result
    assert result["decision"] == existing_decision

    fraud_mock.assert_not_called()
    velocity_mock.assert_not_called()
    decision_mock.assert_not_called()

    pipeline.fraud_state_service.get_customer_profile.assert_not_called()
    pipeline.fraud_state_service.get_recent_transactions.assert_not_called()
    pipeline.fraud_state_service.learn_from_transaction.assert_not_called()
    pipeline.fraud_state_service.persist_transaction.assert_not_called()


def test_concurrent_duplicate_does_not_mutate_state_after_conditional_write_conflict():
    pipeline = PipelineService()

    transaction = make_transaction()
    profile = MagicMock()
    velocity_result = MagicMock()
    fraud_result = make_fraud_result()
    decision = make_decision()

    winning_result = MagicMock()
    winning_result.transaction_reference = (
        transaction.transaction_reference
    )

    winning_decision = {
        "decision": "DECLINE",
        "decision_reason": "Risk score exceeds the automatic decline threshold.",
        "risk_score": 82,
        "risk_level": "HIGH",
        "is_fraud": True,
        "velocity_violation": True,
    }

    pipeline.fraud_repository.get_result = MagicMock(
        side_effect=[
            None,
            {
                "fraud_result": winning_result,
                "decision": winning_decision,
            },
        ]
    )

    pipeline.fraud_repository.insert_result_if_absent = MagicMock(
        return_value=False
    )

    pipeline.fraud_state_service.get_customer_profile = MagicMock(
        return_value=profile
    )
    pipeline.fraud_state_service.get_recent_transactions = MagicMock(
        return_value=[]
    )
    pipeline.fraud_state_service.learn_from_transaction = MagicMock()
    pipeline.fraud_state_service.persist_transaction = MagicMock()

    with patch.object(
        pipeline.velocity_engine,
        "score",
        return_value=velocity_result,
    ), patch.object(
        pipeline.fraud_engine,
        "evaluate",
        return_value=fraud_result,
    ), patch.object(
        pipeline,
        "determine_decision",
        return_value=decision,
    ):
        result = pipeline.process_existing_transaction(transaction)

    assert result["fraud_result"] is winning_result
    assert result["decision"] == winning_decision

    pipeline.fraud_state_service.learn_from_transaction.assert_not_called()
    pipeline.fraud_state_service.persist_transaction.assert_not_called()

    pipeline.fraud_repository.insert_result_if_absent.assert_called_once_with(
        result=fraud_result,
        decision=decision,
    )
