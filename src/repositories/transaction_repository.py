from sqlalchemy import text

from src.services.database import get_session
from src.sql.transaction_queries import (
    INSERT_TRANSACTION,
    COUNT_TRANSACTIONS,
    GET_RANDOM_CUSTOMER,
)


class TransactionRepository:

    def insert_transaction(self, transaction):

        session = get_session()

        try:

            result = session.execute(
                text(INSERT_TRANSACTION),
                transaction.to_dict(),
            )

            transaction_id = result.scalar()

            session.commit()

            return transaction_id

        finally:
            session.close()

    def count_transactions(self):

        session = get_session()

        try:

            result = session.execute(
                text(COUNT_TRANSACTIONS)
            )

            return result.scalar()

        finally:
            session.close()

    def get_random_customer_id(self):

        session = get_session()

        try:

            result = session.execute(
                text(GET_RANDOM_CUSTOMER)
            )

            row = result.fetchone()

            if row:
                return row[0]

            return None

        finally:
            session.close()