import logging

from src.logging_config import setup_logging
from src.services.metrics_service import MetricsService
from src.services.request_router import RequestRouter

setup_logging()

logger = logging.getLogger(__name__)

router = RequestRouter()


def lambda_handler(event, context):
    """
    AWS Lambda entry point.

    Delegates request handling to the RequestRouter.
    """

    logger.info("Received Lambda invocation.")

    try:

        return router.handle(event)

    except Exception:

        logger.exception("Unhandled Lambda exception.")

        MetricsService.lambda_failure()

        raise