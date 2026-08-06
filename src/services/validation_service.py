from ipaddress import ip_address


class ValidationError(Exception):
    """
    Raised whenever an incoming API request is invalid.
    """
    pass


class ValidationService:

    REQUIRED_FIELDS = [
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

        #
        # Required fields
        #

        for field in self.REQUIRED_FIELDS:

            if field not in payload:

                raise ValidationError(
                    f"Missing required field: {field}"
                )

        #
        # customer_id
        #

        if not isinstance(payload["customer_id"], int):

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

        if not payload["merchant_name"].strip():

            raise ValidationError(
                "merchant_name cannot be empty"
            )

        #
        # merchant_category
        #

        if not payload["merchant_category"].strip():

            raise ValidationError(
                "merchant_category cannot be empty"
            )

        #
        # payment method
        #

        if (
            payload["payment_method"]
            not in self.VALID_PAYMENT_METHODS
        ):

            raise ValidationError(
                "Unsupported payment_method"
            )

        #
        # status
        #

        if (
            payload["status"]
            not in self.VALID_STATUS
        ):

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

        return True