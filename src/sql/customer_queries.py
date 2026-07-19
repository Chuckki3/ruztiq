INSERT_CUSTOMER = """
INSERT INTO customers (
    first_name,
    last_name,
    email,
    phone,
    state,
    account_age_days,
    device_preference
)
VALUES (
    :first_name,
    :last_name,
    :email,
    :phone,
    :state,
    :account_age_days,
    :device_preference
)
"""

COUNT_CUSTOMERS = """
SELECT COUNT(*)
FROM customers
"""