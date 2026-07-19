from src.generators.customer_generator import generate_customer
from src.repositories.customer_repository import CustomerRepository


def main():

    repository = CustomerRepository()

    customer = generate_customer()

    repository.save(customer)

    total = repository.count()

    print("Customer inserted successfully.")
    print(customer)
    print(f"Total customers: {total}")


if __name__ == "__main__":
    main()