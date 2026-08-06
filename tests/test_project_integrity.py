import importlib


MODULES = [
    "src.models.api_transaction",
    "src.models.transaction",
    "src.models.fraud_result",

    "src.generators.transactions_generator",

    "src.repositories.transaction_repository",
    "src.repositories.fraud_repository",

    "src.fraud.fraud_engine",

    "src.services.dynamodb",
    "src.services.metrics_service",
    "src.services.validation_service",
    "src.services.pipeline_service",
    "src.services.request_router",

    "src.lambda_function.handler",
]


def test_project_imports():

    failed = []

    for module in MODULES:

        try:
            importlib.import_module(module)

        except Exception as exc:
            failed.append(f"{module}: {exc}")

    assert failed == [], "\n".join(failed)