from src.generators.transactions_generator import generate_transaction
from src.fraud.fraud_engine import FraudEngine

transaction = generate_transaction(customer_id=1)

engine = FraudEngine()

result = engine.evaluate(transaction)

print(transaction)

print()

print(result)

print()

print(result.risk_score)
print(result.risk_level)
print(result.reasons)