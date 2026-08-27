from datetime import datetime
from ipaddress import ip_address


class ValidationError(Exception):
    """
    Raised whenever an incoming API request is invalid.
    """

    pass


class ValidationService:
    REQUIRED_FIELDS = [
        "transaction_reference",
        "customer_id",
        "amount",
        "merchant_name",
        "merchant_category",
        "payment_method",
        "device_type",
        "location",
        "ip_address",
        "status",
    ]

    VALID_PAYMENT_METHODS = {
        "CARD",
        "TRANSFER",
        "USSD",
    }

    VALID_STATUS = {
        "APPROVED",
        "FAILED",
    }

    def validate(self, payload):
        """
        Validate an incoming fraud-scoring API request.
        """

        if not isinstance(payload, dict):
            raise ValidationError(
                "Request body must be a JSON object"
            )

        #
        # Required fields
        #
        for field in self.REQUIRED_FIELDS:
            if field not in payload:
                raise ValidationError(
                    f"Missing required field: {field}"
                )

        #
        # transaction_reference
        #
        if not isinstance(
            payload["transaction_reference"],
            str,
        ):
            raise ValidationError(
                "transaction_reference must be a string"
            )

        if not payload["transaction_reference"].strip():
            raise ValidationError(
                "transaction_reference cannot be empty"
            )

        #
        # customer_id
        #
        if not isinstance(
            payload["customer_id"],
            int,
        ):
            raise ValidationError(
                "customer_id must be an integer"
            )

        #
        # amount
        #
        if not isinstance(
            payload["amount"],
            (int, float),
        ):
            raise ValidationError(
                "amount must be numeric"
            )

        if payload["amount"] <= 0:
            raise ValidationError(
                "amount must be greater than zero"
            )

        #
        # merchant_name
        #
        if not isinstance(
            payload["merchant_name"],
            str,
        ) or not payload["merchant_name"].strip():
            raise ValidationError(
                "merchant_name cannot be empty"
            )

        #
        # merchant_category
        #
        if not isinstance(
            payload["merchant_category"],
            str,
        ) or not payload["merchant_category"].strip():
            raise ValidationError(
                "merchant_category cannot be empty"
            )

        #
        # payment method
        #
        payment_method = str(
            payload["payment_method"]
        ).upper()

        if payment_method not in self.VALID_PAYMENT_METHODS:
            raise ValidationError(
                "Unsupported payment_method"
            )

        #
        # status
        #
        status = str(
            payload["status"]
        ).upper()

        if status not in self.VALID_STATUS:
            raise ValidationError(
                "Unsupported status"
            )

        #
        # IP address
        #
        try:
            ip_address(
                payload["ip_address"]
            )
        except ValueError:
            raise ValidationError(
                "Invalid IP address"
            )

        #
        # Optional transaction timestamp
        #
        if payload.get("transaction_time") is not None:
            if not isinstance(
                payload["transaction_time"],
                str,
            ):
                raise ValidationError(
                    "transaction_time must be a string"
                )

            try:
                datetime.fromisoformat(
                    payload["transaction_time"]
                )
            except ValueError:
                raise ValidationError(
                    "Invalid transaction_time"
                )

        #
        # Optional currency
        #
        if payload.get("currency") is not None:
            if not isinstance(
                payload["currency"],
                str,
            ) or not payload["currency"].strip():
                raise ValidationError(
                    "currency cannot be empty"
                )

        #
        # Optional merchant_id
        #
        if payload.get("merchant_id") is not None:
            if not isinstance(
                payload["merchant_id"],
                str,
            ) or not payload["merchant_id"].strip():
                raise ValidationError(
                    "merchant_id cannot be empty"
                )

        #
        # Optional device_id
        #
        if payload.get("device_id") is not None:
            if not isinstance(
                payload["device_id"],
                str,
            ) or not payload["device_id"].strip():
                raise ValidationError(
                    "device_id cannot be empty"
                )

        return True