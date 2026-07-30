MODULES = [
    "src.config",
    "src.services.database",
    "src.models.customer",
    "src.models.transaction",
    "src.models.fraud_result",
    "src.generators.customer_generator",
    "src.generators.transactions_generator",
    "src.repositories.customer_repository",
    "src.repositories.transaction_repository",
    "src.repositories.fraud_repository",
    "src.services.fraud_engine",
    "src.services.pipeline_service",
]


def main():

    import importlib

    print("=" * 50)
    print("PROJECT INTEGRITY CHECK")
    print("=" * 50)

    passed = 0

    for module in MODULES:

        try:

            importlib.import_module(module)

            print(f"✓ {module}")

            passed += 1

        except Exception as e:

            print(f"✗ {module}")
            print(f"  {e}")

    print("\n")
    print(f"{passed}/{len(MODULES)} modules imported successfully.")


if __name__ == "__main__":
    main()