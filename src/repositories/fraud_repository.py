from sqlalchemy import text

from src.services.database import get_session
from src.sql.fraud_queries import (
    INSERT_FRAUD_RESULT,
    COUNT_RESULTS,
)


class FraudRepository:

    def insert_result(self, result):

        session = get_session()

        try:

            session.execute(
                text(INSERT_FRAUD_RESULT),
                result.to_dict(),
            )

            session.commit()

        finally:
            session.close()

    def count_results(self):

        session = get_session()

        try:

            result = session.execute(
                text(COUNT_RESULTS)
            )

            return result.scalar()

        finally:
            session.close()