from src.generators.transactions_generator import generate_transaction
from src.repositories.transaction_repository import TransactionRepository
from src.repositories.fraud_repository import FraudRepository
from src.services.fraud_engine import FraudEngine


class PipelineService:

    def __init__(self):
        self.transaction_repo = TransactionRepository()
        self.fraud_repo = FraudRepository()
        self.engine = FraudEngine()

    def process_one_transaction(self):

        customer_id = self.transaction_repo.get_random_customer_id()

        if customer_id is None:
            print("No customers found.")
            return

        transaction = generate_transaction(customer_id)

        transaction_id = self.transaction_repo.insert_transaction(
            transaction
        )

        fraud_result = self.engine.score_transaction(
            transaction,
            transaction_id,
        )

        self.fraud_repo.insert_result(
            fraud_result
        )

        print("\nTransaction")
        print(transaction)

        print("\nFraud Result")
        print(fraud_result)

        print("\nPipeline completed successfully.")

    def process_batch(self, batch_size=100):

        successful = 0

        for _ in range(batch_size):

            customer_id = self.transaction_repo.get_random_customer_id()

            if customer_id is None:
                continue

            transaction = generate_transaction(customer_id)

            transaction_id = self.transaction_repo.insert_transaction(
                transaction
            )

            fraud_result = self.engine.score_transaction(
                transaction,
                transaction_id,
            )

            self.fraud_repo.insert_result(
                fraud_result
            )

            successful += 1

        print("\nBatch completed successfully.")
        print(f"Transactions processed: {successful}")