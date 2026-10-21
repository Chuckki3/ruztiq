# RuztIQ Fraud Detection API

Version: 1.0.0
API style: REST over HTTPS
Primary operation: Score a transaction for potential fraud
Runtime: AWS API Gateway, AWS Lambda, and DynamoDB

## 1. Overview

RuztIQ evaluates a submitted transaction using transaction attributes, available customer history, behavioural signals, and transaction velocity. It returns a risk score, risk classification, fraud flag, explanatory reasons, and an operational decision.

The API distinguishes between:

- **Fraud evaluation:** `risk_score`, `risk_level`, `is_fraud`, and `reasons`.
- **Operational decision:** `decision` and `decision_reason`.
- **Velocity analysis:** `velocity_violation`.

These outputs are related but are not interchangeable.

## 2. Endpoint

| Property | Value |
|---|---|
| Method | `POST` |
| Path | `/score` |
| Content type | `application/json` |
| Authentication | Bearer token |
| Success response | `200 OK` |
| Request validation failure | `400 Bad Request` |

The deployed endpoint is exposed through the `ApiEndpoint` output in the AWS CloudFormation/SAM stack. Its general form is:

`https://{api-id}.execute-api.{region}.amazonaws.com/Prod/score`

Replace the placeholders with the actual deployed values. Do not treat the template pattern as a live endpoint.

## 3. Authentication

Supply the API credential in the HTTP `Authorization` header:

`Authorization: Bearer <token>`

The AWS Lambda REQUEST authorizer:

1. Reads the `Authorization` header without regard to header-name casing.
2. Extracts a case-insensitive `Bearer` scheme and token.
3. Retrieves the expected token from AWS Secrets Manager.
4. Compares the supplied token with the expected token using `hmac.compare_digest`.
5. Returns an API Gateway Allow or Deny policy.

The secret's `SecretString` is expected to contain JSON with a non-empty string property named `token`, for example:

    {
      "token": "<configured-token>"
    }

**Deployment configuration note:** the authorizer code defaults to the secret name `sentineliq/api/auth`. The infrastructure template also sets `API_AUTH_SECRET_NAME` to that value and grants access to the secret identified by the `ApiAuthSecretArn` parameter. Ensure the name and ARN refer to the same secret in the target environment.

The authorizer returns an IAM policy, not an application-level JSON error. The final HTTP status and response body for rejected requests are determined by API Gateway configuration. Do not assume a fixed error body for authorization failures.

## 4. Request body

Submit a JSON object with the following fields.

| Field | JSON type | Required by current validator | Description |
|---|---|---:|---|
| `transaction_reference` | string | Yes | Unique transaction reference; also used as the idempotency key |
| `customer_id` | integer | Yes | Customer identifier |
| `amount` | number | Yes | Transaction amount; must be greater than zero |
| `merchant_name` | string | Yes | Merchant name; must not be blank |
| `merchant_category` | string | Yes | Merchant category; must not be blank |
| `payment_method` | string | Yes | Supported values: `CARD`, `TRANSFER`, `USSD` |
| `device_type` | string | Yes | Device type associated with the transaction |
| `location` | string | Yes | Transaction location |
| `ip_address` | string | Yes | Valid IPv4 or IPv6 address |
| `status` | string | Yes | Supported values: `APPROVED`, `FAILED` |
| `transaction_time` | string | No | ISO 8601 timestamp; omitted or null means current UTC time |
| `currency` | string | No | Non-empty currency value when provided |
| `merchant_id` | string | No | Non-empty merchant identifier when provided |
| `device_id` | string | No | Non-empty device identifier when provided |

The table describes the current validator and model together. In particular, `status` is required by request validation even though the Python dataclass defines a default value.

### Timestamp handling

`transaction_time` is parsed with Python's ISO 8601 `datetime.fromisoformat` implementation.

- A timestamp with a UTC offset is converted to UTC.
- A timestamp without an offset is interpreted as UTC.
- If omitted or null, the application uses the current UTC time.
- The supplied timestamp represents the transaction time used by the internal pipeline; it is not automatically replaced with the request receipt time when a valid value is supplied.

Example: `2026-08-27T18:30:00+01:00` becomes `2026-08-27T17:30:00+00:00`.

### Fields not currently used by the internal transaction model

`currency`, `merchant_id`, and `device_id` are accepted and validated when supplied, but `APITransaction.to_transaction()` does not transfer them into the internal `Transaction` object. Do not assume they currently affect scoring or customer learning.

### Validation limitations

The current implementation does not enforce a strict currency format, string-length limits, or a documented list of merchant categories and device types. It also does not explicitly reject unknown request properties in `ValidationService`; however, the subsequent `APITransaction(**body)` construction can fail for an unknown property. That failure is not converted into the router's normal validation `400` response.

The implementation also lacks explicit finite-number validation for `amount` and explicit boolean rejection for integer/numeric fields. Clients should send a genuine integer for `customer_id` and a finite, positive number for `amount`.

## 5. Example request

    {
      "transaction_reference": "API-TEST123456",
      "customer_id": 1001,
      "amount": 25000.00,
      "currency": "NGN",
      "merchant_id": "MERCHANT-001",
      "merchant_name": "Test Merchant",
      "merchant_category": "RETAIL",
      "device_id": "DEVICE-001",
      "device_type": "MOBILE",
      "location": "Lagos, Nigeria",
      "transaction_time": "2026-08-27T18:30:00+01:00",
      "payment_method": "CARD",
      "ip_address": "197.210.70.10",
      "status": "APPROVED"
    }

## 6. Successful response

A successful scoring request returns HTTP `200` with a JSON body containing these fields:

| Field | Type | Meaning |
|---|---|---|
| `transaction_reference` | string | Reference associated with the evaluated fraud result |
| `risk_score` | number | Calculated fraud risk score |
| `risk_level` | string | `LOW`, `MEDIUM`, or `HIGH` |
| `is_fraud` | boolean | Whether the fraud engine's score meets its fraud threshold |
| `reasons` | string | Comma-separated explanations, or `No suspicious activity` when no reasons were generated |
| `decision` | string | `APPROVE`, `REVIEW`, or `DECLINE` |
| `decision_reason` | string | Explanation for the operational decision |
| `velocity_violation` | boolean | Whether the configured transaction-velocity threshold was exceeded |

Example response:

    {
      "transaction_reference": "API-TEST123456",
      "risk_score": 30,
      "risk_level": "MEDIUM",
      "is_fraud": false,
      "reasons": "Late Night Transaction, New Device",
      "decision": "APPROVE",
      "decision_reason": "Transaction is below the configured review threshold.",
      "velocity_violation": false
    }

This is an illustrative response showing the response structure, not a guaranteed score for the example request. Actual scores and reasons depend on the transaction time, profile, history, and scoring rules.

## 7. Risk scoring

The current fraud engine applies additive scoring rules. Confirmed rule weights and thresholds include:

| Signal | Score contribution / condition |
|---|---|
| High amount | +30 when amount is strictly greater than 150,000 |
| Late-night transaction | +15 for hours 00:00 through 05:59, based on the transaction timestamp |
| Entertainment category | +10 when category is exactly `Entertainment` and amount is greater than 5,000 |
| High-value USSD | +15 when payment method is `USSD` and amount is greater than 100,000 |
| Failed payment | +20 when status is `FAILED` |
| New device | +20 when a customer profile exists and the device is unseen |
| New location | +20 when a customer profile exists and the location is unseen |
| New IP address | +15 when a customer profile exists and the IP is unseen |
| New merchant | +10 when a customer profile exists and the merchant is unseen |
| Spending anomaly | +30 when the profile has at least 10 transactions, average amount is positive, and the current amount is more than five times that average |
| Repeated failed payments | +25 when the profile has at least five failed transactions |
| Velocity violation | Adds the score returned by the velocity engine; currently +25 for a violation |

Some profile-based rules only apply when a customer profile exists. The engine's rules use the values and comparisons implemented in code; category comparisons should not be assumed case-insensitive.

### Risk levels

| Score | `risk_level` |
|---:|---|
| 0–29 | `LOW` |
| 30–59 | `MEDIUM` |
| 60 and above | `HIGH` |

The fraud flag is separately set to `true` when the fraud score is at least `50`.

## 8. Operational decision policy

The decision engine applies the following hierarchy:

1. A score of 80 or higher results in `DECLINE`.
2. Otherwise, a transaction flagged as fraud with a score of at least 40 results in `DECLINE`.
3. Otherwise, a velocity violation results in `REVIEW`.
4. Otherwise, a score of 40 or higher results in `REVIEW`.
5. All other transactions result in `APPROVE`.

Consequently, a transaction can be `MEDIUM` risk and still be flagged as fraud. A fraud flag alone does not always cause a decline: the score and the decision hierarchy determine the final outcome.

The decision policy is an application rule, not a guarantee that a downstream bank, issuer, or payment processor will execute the decision.

## 9. Transaction velocity

The current velocity engine uses a five-minute window and a threshold of five historical transactions. It counts history records whose timestamps fall within the inclusive interval from the target transaction time minus five minutes through the target transaction time.

A violation occurs when the number of qualifying history records is greater than or equal to five. The violation adds 25 points to the fraud score and can force the operational decision to `REVIEW` unless a higher-priority decline rule applies.

This describes the configured engine. Actual history availability depends on the persisted transaction data returned by the state service.

## 10. Idempotency and duplicate references

`transaction_reference` is the idempotency key.

- The pipeline first looks for an existing fraud result for that reference.
- If one exists, the saved fraud result and decision snapshot are returned without repeating customer learning or transaction persistence.
- If no result exists, the pipeline evaluates the transaction and conditionally writes the result using DynamoDB's `attribute_not_exists(transaction_reference)` condition.
- If another concurrent request wins the conditional write, the losing request retrieves and returns the saved result.

A duplicate request normally follows the same HTTP `200` response structure; there is no documented `duplicate` flag in the response.

The implementation does not compare the new payload with the payload that originally used the reference. Clients should therefore use a stable, unique reference for each logical transaction and should not reuse it for a different transaction.

The conditional write protects fraud-result creation only. It does not make fraud-result storage, customer-profile learning, transaction persistence, and metric emission a single atomic operation.

## 11. Errors

### Invalid JSON

HTTP `400`

    {
      "error": "Invalid JSON body"
    }

### Invalid request

HTTP `400`, with a JSON object containing an `error` string. Examples of current validation messages include:

- `Request body must be a JSON object`
- `Missing required field: transaction_reference`
- `transaction_reference must be a string`
- `transaction_reference cannot be empty`
- `customer_id must be an integer`
- `amount must be numeric`
- `amount must be greater than zero`
- `merchant_name cannot be empty`
- `merchant_category cannot be empty`
- `Unsupported payment_method`
- `Unsupported status`
- `Invalid IP address`
- `transaction_time must be a string`
- `Invalid transaction_time`
- `currency cannot be empty`
- `merchant_id cannot be empty`
- `device_id cannot be empty`

The first encountered validation failure is returned; this is not a comprehensive list of every possible runtime failure.

### Authentication failure

The Lambda authorizer returns a Deny policy for missing/malformed credentials, invalid tokens, or failure to retrieve a usable secret. API Gateway determines the HTTP response status and body. Depending on API Gateway's handling and configuration, clients may receive an authorization-related `401` or `403`.

### Unexpected processing failure

The main Lambda handler logs the exception, emits a Lambda failure metric, and re-raises it. The API response is therefore governed by API Gateway's integration and gateway-response configuration; a custom JSON `500` body is not implemented in the shown handler.

## 12. Rate limits and infrastructure

The SAM template configures `/score` POST throttling with:

- Rate limit: 20 requests per second.
- Burst limit: 40 requests.

These are API Gateway throttling settings, not a promise of unlimited sustained throughput. Throttling behavior and client-visible responses are controlled by AWS API Gateway.

The template provisions DynamoDB tables for transactions, customer profiles, and fraud results, and CloudWatch alarms for Lambda errors/throttles and API Gateway errors/latency.

## 13. Scope and implementation notes

- The documented public scoring route is `POST /score`.
- The Lambda router also supports a non-API batch invocation path when an event has no `body`; that internal invocation path is not documented as a public HTTP endpoint.
- The request and response contracts here reflect the current source code reviewed for this documentation.
- If validation behavior, model fields, decision thresholds, authentication settings, or deployment infrastructure change, update this file and `openapi.yaml` together.
