import json
import logging

from src.models.api_transaction import APITransaction
from src.services.metrics_service import MetricsService
from src.services.pipeline_service import PipelineService
from src.services.validation_service import (
    ValidationService,
    ValidationError,
)

logger = logging.getLogger(__name__)


class RequestRouter:
    """
    Routes Lambda events to the appropriate pipeline.
    """

    def __init__(self):
        self.pipeline = PipelineService()
        self.validator = ValidationService()

    def handle(self, event):
        """
        Route API Gateway requests or batch invocations.
        """

        event = event or {}

        #
        # API Request metric
        #
        MetricsService.api_request()

        #
        # API Gateway request
        #
        if "body" in event:

            body = event["body"]

            if isinstance(body, str):
                body = json.loads(body)

            #
            # Validate request
            #
            try:

                self.validator.validate(body)

            except ValidationError as e:

                MetricsService.validation_error()

                return {
                    "statusCode": 400,
                    "body": json.dumps(
                        {
                            "error": str(e)
                        }
                    ),
                }

            api_transaction = APITransaction(**body)

            result = self.pipeline.process_existing_transaction(
                api_transaction.to_transaction()
            )

            fraud = result["fraud_result"]

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "transaction_reference":
                            fraud.transaction_reference,
                        "risk_score":
                            fraud.risk_score,
                        "risk_level":
                            fraud.risk_level,
                        "is_fraud":
                            fraud.is_fraud,
                        "reasons":
                            fraud.reasons,
                    }
                ),
            }

        #
        # Batch processing
        #
        batch_size = int(
            event.get("batch_size", 100)
        )

        processed = self.pipeline.process_batch(
            batch_size=batch_size
        )

        return {
            "statusCode": 200,
            "transactions_processed": processed,
        }