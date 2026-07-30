INSERT_TRANSACTION = """
INSERT INTO transactions (
    customer_id,
    transaction_reference,
    amount,
    merchant_name,
    merchant_category,
    payment_method,
    device_type,
    transaction_time,
    location,
    ip_address,
    status
)
VALUES (
    :customer_id,
    :transaction_reference,
    :amount,
    :merchant_name,
    :merchant_category,
    :payment_method,
    :device_type,
    :transaction_time,
    :location,
    :ip_address,
    :status
)
RETURNING transaction_id;
"""


COUNT_TRANSACTIONS = """
SELECT COUNT(*)
FROM transactions;
"""


GET_RANDOM_CUSTOMER = """
SELECT customer_id
FROM customers
ORDER BY RANDOM()
LIMIT 1;
"""