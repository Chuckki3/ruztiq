from sqlalchemy import text

from src.services.database import get_session
from src.sql.fraud_queries import (
    INSERT_FRAUD_RESULT,
    COUNT_FRAUD_RESULTS,
)


class FraudRepository:

    def insert_result(self, fraud_result):

        session = get_session()

        try:

            session.execute(
                text(INSERT_FRAUD_RESULT),
                fraud_result.to_dict(),
            )

            session.commit()

        finally:

            session.close()

    def count_results(self):

        session = get_session()

        try:

            result = session.execute(
                text(COUNT_FRAUD_RESULTS)
            )

            return result.scalar()

        finally:

            session.close()