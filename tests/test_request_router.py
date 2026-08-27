import json

from unittest.mock import MagicMock, patch

from src.services.request_router import RequestRouter


def valid_payload():
    return {
        "transaction_reference": "API-TEST123456",
        "customer_id": 1001,
        "amount": 25000.00,
        "currency": "NGN",
        "merchant_id": "MERCHANT-001",
        "merchant_name": "Test Merchant",
        "merchant_category": "RETAIL",
        "device_id": "DEVICE-001",
        "device_type": "MOBILE",
        "location": "Lagos, Nigeria",
        "transaction_time": "2026-08-27T18:30:00+01:00",
        "payment_method": "CARD",
        "ip_address": "197.210.70.10",
        "status": "APPROVED",
    }


@patch("src.services.request_router.PipelineService")
@patch("src.services.request_router.MetricsService")
def test_valid_api_request(mock_metrics, mock_pipeline):
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

    assert response["statusCode"] == 200

    body = json.loads(response["body"])

    assert body["transaction_reference"] == "API-TEST123456"
    assert body["risk_score"] == 18.5
    assert body["risk_level"] == "LOW"
    assert body["is_fraud"] is False
    assert body["reasons"] == []

    mock_pipeline_instance.process_existing_transaction.assert_called_once()

    transaction = (
        mock_pipeline_instance
        .process_existing_transaction
        .call_args.args[0]
    )

    assert transaction.transaction_reference == "API-TEST123456"
    assert transaction.customer_id == 1001
    assert transaction.amount == 25000.00
    assert transaction.merchant_name == "Test Merchant"
    assert transaction.merchant_category == "RETAIL"
    assert transaction.payment_method == "CARD"
    assert transaction.device_type == "MOBILE"
    assert transaction.location == "Lagos, Nigeria"
    assert transaction.ip_address == "197.210.70.10"
    assert transaction.status == "APPROVED"


@patch("src.services.request_router.MetricsService")
def test_invalid_api_request_returns_400(mock_metrics):
    router = RequestRouter()

    payload = valid_payload()
    payload["payment_method"] = "INVALID"

    event = {
        "body": json.dumps(payload)
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

    mock_pipeline.return_value.process_existing_transaction.assert_not_called()


@patch("src.services.request_router.MetricsService")
def test_missing_transaction_reference_returns_400(mock_metrics):
    router = RequestRouter()

    payload = valid_payload()
    del payload["transaction_reference"]

    event = {
        "body": json.dumps(payload)
    }

    response = router.handle(event)

    assert response["statusCode"] == 400

    body = json.loads(response["body"])

    assert body["error"] == (
        "Missing required field: transaction_reference"
    )

    mock_metrics.validation_error.assert_called_once()


@patch("src.services.request_router.MetricsService")
def test_invalid_transaction_time_returns_400(mock_metrics):
    router = RequestRouter()

    payload = valid_payload()
    payload["transaction_time"] = "not-a-timestamp"

    event = {
        "body": json.dumps(payload)
    }

    response = router.handle(event)

    assert response["statusCode"] == 400

    body = json.loads(response["body"])

    assert body["error"] == "Invalid transaction_time"

    mock_metrics.validation_error.assert_called_once()
