import boto3
import logging

logger = logging.getLogger(__name__)

cloudwatch = boto3.client("cloudwatch")


class MetricsService:
    """
    Publishes custom CloudWatch metrics for RuztIQ.
    """

    NAMESPACE = "RuztIQ"

    @classmethod
    def publish_metric(
        cls,
        metric_name: str,
        value: float,
        unit: str = "Count",
    ):

        try:

            cloudwatch.put_metric_data(
                Namespace=cls.NAMESPACE,
                MetricData=[
                    {
                        "MetricName": metric_name,
                        "Value": value,
                        "Unit": unit,
                    }
                ],
            )

        except Exception:

            logger.exception(
                "Unable to publish metric %s",
                metric_name,
            )

    @classmethod
    def transaction_processed(cls):

        cls.publish_metric(
            "TransactionsProcessed",
            1,
        )

    @classmethod
    def fraud_detected(cls):

        cls.publish_metric(
            "FraudDetected",
            1,
        )

    @classmethod
    def fraud_score(
        cls,
        score,
    ):

        cls.publish_metric(
            "FraudScore",
            score,
        )

    @classmethod
    def api_request(cls):

        cls.publish_metric(
            "ApiRequests",
            1,
        )

    @classmethod
    def validation_error(cls):

        cls.publish_metric(
            "ValidationErrors",
            1,
        )

    @classmethod
    def lambda_failure(cls):

        cls.publish_metric(
            "LambdaFailures",
            1,
        )