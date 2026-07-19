from sqlalchemy import text

from src.models.customer import Customer
from src.services.database import get_session
from src.sql.customer_queries import (
    INSERT_CUSTOMER,
    COUNT_CUSTOMERS,
)


class CustomerRepository:
    """Handles customer persistence."""

    def save(self, customer: Customer):
        session = get_session()

        try:
            session.execute(
                text(INSERT_CUSTOMER),
                customer.to_dict()
            )

            session.commit()

        except Exception:
            session.rollback()
            raise

        finally:
            session.close()

    def count(self):

        session = get_session()

        try:
            result = session.execute(
                text(COUNT_CUSTOMERS)
            )

            return result.scalar()

        finally:
            session.close()