from src.generators.transactions_generator import generate_transaction
from src.repositories.transaction_repository import TransactionRepository


def main():
    repository = TransactionRepository()

    customer_id = repository.get_random_customer_id()

    if customer_id is None:
        print("No customers found in the database.")
        return

    transaction = generate_transaction(customer_id)

    repository.insert_transaction(transaction)

    total = repository.count_transactions()

    print("Transaction inserted successfully.\n")
    print(transaction)
    print(f"\nTotal transactions: {total}")


if __name__ == "__main__":
    main()