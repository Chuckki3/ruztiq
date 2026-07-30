import logging


def setup_logging():
    """
    Configure application logging for local execution
    and AWS Lambda.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=(
            "%(asctime)s | "
            "%(levelname)s | "
            "%(name)s | "
            "%(message)s"
        ),
    )

    return logging.getLogger("fraud_detection")