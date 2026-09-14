from src.profiles.customer_profile_service import (
    CustomerProfileService,
)
from src.repositories.transaction_repository import (
    TransactionRepository,
)


class FraudStateService:
    """
    Provides the operational customer state required by RuztIQ.

    This service creates a persistence boundary between the fraud
    decision pipeline and the underlying storage implementation.

    The fraud engines do not know where customer state comes from.
    PipelineService should interact with this service instead of
    reaching directly into DynamoDB-backed repositories.

    Current implementation:

        FraudStateService
                ↓
        DynamoDB-backed repositories

    Future implementations may use another operational state store
    without requiring changes to FraudEngine, VelocityEngine or
    DecisionEngine.
    """

    def __init__(
        self,
        profile_service=None,
        transaction_repository=None,
    ):
        """
        Initialise the operational fraud state provider.

        Dependencies remain injectable so the service can be
        independently unit tested and replaced in future.
        """
        self.profile_service = (
            profile_service
            if profile_service is not None
            else CustomerProfileService()
        )

        self.transaction_repository = (
            transaction_repository
            if transaction_repository is not None
            else TransactionRepository()
        )

    # ==========================================================
    # CUSTOMER PROFILE
    # ==========================================================

    def get_customer_profile(
        self,
        customer_id,
    ):
        """
        Retrieve an existing customer profile or create one.

        The profile represents behavioural state accumulated
        from transactions processed before the current transaction.
        """
        return self.profile_service.repository.get_or_create(
            customer_id
        )

    # ==========================================================
    # RECENT TRANSACTION HISTORY
    # ==========================================================

    def get_recent_transactions(
        self,
        customer_id,
        transaction_time,
        window_minutes,
    ):
        """
        Retrieve historical transactions for velocity analysis.

        The current transaction is not persisted until after fraud
        evaluation, so this history represents prior activity.
        """
        return self.transaction_repository.get_recent_transactions(
            customer_id=customer_id,
            transaction_time=transaction_time,
            window_minutes=window_minutes,
        )

    # ==========================================================
    # CUSTOMER LEARNING
    # ==========================================================

    def learn_from_transaction(
        self,
        transaction,
    ):
        """
        Update the customer's behavioural state after the
        transaction has been evaluated.
        """
        return self.profile_service.learn(
            transaction
        )

    # ==========================================================
    # TRANSACTION PERSISTENCE
    # ==========================================================

    def persist_transaction(
        self,
        transaction,
    ):
        """
        Persist the evaluated transaction for future historical
        and velocity analysis.
        """
        return self.transaction_repository.insert_transaction(
            transaction
        )

    # ==========================================================
    # SYNTHETIC TRANSACTION SUPPORT
    # ==========================================================

    def get_random_customer_id(self):
        """
        Return a customer identifier for synthetic transaction
        generation.

        This preserves the existing development/demo behaviour
        while keeping transaction-state access behind the state
        boundary.
        """
        return self.transaction_repository.get_random_customer_id()