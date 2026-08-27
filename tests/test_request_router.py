import json

from unittest.mock import MagicMock, patch

from src.services.request_router import RequestRouter


def valid_payload():
    return {
        "transaction_reference": "TEST-TRANSACTION-001",
        "customer_id": 1001,
        "amount": 25000.00,
        "merchant_name": "Test Merchant",
        "merchant_category": "RETAIL",
        "payment_method": "CARD",
        "device_type": "MOBILE",
        "location": "Lagos, Nigeria",
        "ip_address": "197.210.70.10",
        "status": "APPROVED",
    }


@patch("src.services.request_router.PipelineService")
@patch("src.services.request_router.MetricsService")
def test_valid_api_request(mock_metrics, mock_pipeline):

    #
    # Mock the pipeline so this test focuses on
    # RequestRouter behaviour.
    #

    mock_fraud_result = MagicMock()

    mock_fraud_result.transaction_reference = "API-TEST123456"
    mock_fraud_result.risk_score = 18.5
    mock_fraud_result.risk_level = "LOW"
    mock_fraud_result.is_fraud = False
    mock_fraud_result.reasons = []

    mock_pipeline_instance = mock_pipeline.return_value

    mock_pipeline_instance.process_existing_transaction.return_value = {
        "fraud_result": mock_fraud_result
    }

    router = RequestRouter()

    event = {
        "body": json.dumps(valid_payload())
    }

    response = router.handle(event)

    #
    # HTTP response
    #

    assert response["statusCode"] == 200

    body = json.loads(response["body"])

    #
    # Fraud result
    #

    assert body["transaction_reference"] == "API-TEST123456"
    assert body["risk_score"] == 18.5
    assert body["risk_level"] == "LOW"
    assert body["is_fraud"] is False
    assert body["reasons"] == []

    #
    # Verify pipeline was called
    #

    mock_pipeline_instance.process_existing_transaction.assert_called_once()


@patch("src.services.request_router.MetricsService")
def test_invalid_api_request_returns_400(mock_metrics):

    router = RequestRouter()

    event = {
        "body": json.dumps(
            {
                "customer_id": 1001,
                "amount": 25000.00,
                "merchant_name": "Test Merchant",
                "merchant_category": "RETAIL",
                "payment_method": "INVALID",
                "device_type": "MOBILE",
                "location": "Lagos, Nigeria",
                "ip_address": "197.210.70.10",
                "status": "APPROVED",
            }
        )
    }

    response = router.handle(event)

    assert response["statusCode"] == 400

    body = json.loads(response["body"])

    assert "error" in body
    assert body["error"] == "Unsupported payment_method"

    mock_metrics.validation_error.assert_called_once()


@patch("src.services.request_router.PipelineService")
@patch("src.services.request_router.MetricsService")
def test_invalid_ip_address_returns_400(
    mock_metrics,
    mock_pipeline,
):

    router = RequestRouter()

    payload = valid_payload()

    payload["ip_address"] = "not-an-ip"

    event = {
        "body": json.dumps(payload)
    }

    response = router.handle(event)

    assert response["statusCode"] == 400

    body = json.loads(response["body"])

    assert body["error"] == "Invalid IP address"

    mock_metrics.validation_error.assert_called_once()

    #
    # Pipeline must never receive an invalid transaction.
    #

    mock_pipeline.return_value.process_existing_transaction.assert_not_called()


def test_empty_event_processes_batch():

    router = RequestRouter()

    router.pipeline = MagicMock()

    router.pipeline.process_batch.return_value = 5

    response = router.handle({})

    assert response["statusCode"] == 200
    assert response["transactions_processed"] == 5

    router.pipeline.process_batch.assert_called_once_with(
        batch_size=100
    )
