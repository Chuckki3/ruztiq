from sqlalchemy import text

from src.generators.transactions_generator import generate_transaction
from src.repositories.transaction_repository import TransactionRepository
from src.repositories.fraud_repository import FraudRepository
from src.services.database import get_session
from src.services.fraud_service import FraudService


def main():

    # Step 1: Generate a transaction
    transaction = generate_transaction(customer_id=1)

    # Step 2: Save transaction
    transaction_repo = TransactionRepository()
    transaction_repo.insert(transaction)

    # Step 3: Get the new transaction_id
    session = get_session()

    try:
        transaction_id = session.execute(
            text(
                """
                SELECT transaction_id
                FROM transactions
                WHERE transaction_reference = :reference
                """
            ),
            {"reference": transaction.transaction_reference},
        ).scalar_one()
    finally:
        session.close()

    # Step 4: Evaluate fraud
    service = FraudService()

    fraud_result = service.evaluate_transaction(
        transaction,
        transaction_id=transaction_id,
    )

    # Step 5: Save fraud result
    fraud_repo = FraudRepository()
    fraud_repo.insert(fraud_result)

    print("✓ Fraud result inserted.")
    print(fraud_result)
    print(f"Total fraud results: {fraud_repo.count()}")


if __name__ == "__main__":
    main()