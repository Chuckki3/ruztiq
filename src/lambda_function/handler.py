import logging
import os

from src.logging_config import setup_logging
from src.services.pipeline_service import PipelineService

setup_logging()

logger = logging.getLogger(__name__)


def lambda_handler(event, context):
    """
    AWS Lambda entry point.

    Priority:
    1. event["batch_size"]
    2. Lambda Environment Variable BATCH_SIZE
    3. Default = 100
    """

    event = event or {}

    batch_size = int(
        event.get(
            "batch_size",
            os.getenv("BATCH_SIZE", "100"),
        )
    )

    logger.info(
        "Starting fraud detection pipeline (batch_size=%s)",
        batch_size,
    )

    pipeline = PipelineService()

    processed = pipeline.process_batch(
        batch_size=batch_size
    )

    logger.info(
        "Pipeline completed successfully."
    )

    return {
        "statusCode": 200,
        "transactions_processed": processed,
    }