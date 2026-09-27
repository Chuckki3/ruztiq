# RuztIQ

## Real Time Fintech Fraud Detection and Transaction Decisioning

RuztIQ is a real time fraud detection and transaction decisioning service designed for fintech transaction environments.

It evaluates incoming transactions using transaction level rules, customer behavioural signals and velocity analysis, then returns an actionable decision:

**APPROVE**, **REVIEW**, or **DECLINE**.

The system is designed to sit at the transaction decision point of a fintech system, allowing the fintech to evaluate risk before completing a transaction.

---

## What RuztIQ Does

RuztIQ receives transaction information through an authenticated API and evaluates the transaction against its configured fraud detection rules and available customer history.

The resulting response contains:

* Transaction reference
* Risk score
* Risk level
* Fraud status
* Fraud reasons
* Operational decision
* Decision reason
* Velocity violation status

A typical decision therefore provides both an outcome and the reasoning behind that outcome.

Example:

```json
{
  "transaction_reference": "RZ-LIVE-20260924-HIGH-001",
  "risk_score": 65,
  "risk_level": "HIGH",
  "is_fraud": true,
  "reasons": "High Amount, Late Night, Failed Payment",
  "decision": "DECLINE",
  "decision_reason": "Fraud engine identified the transaction as fraudulent.",
  "velocity_violation": false
}
```

---

## Core Decision Flow

The current decision flow is:

```text
Transaction
     |
     v
API Gateway
     |
     v
Request Authorizer
     |
     v
RuztIQ Lambda
     |
     v
Request Validation
     |
     v
Transaction Conversion
     |
     v
Fraud Detection Pipeline
     |
     +----------------------+
     |                      |
     v                      v
Customer Behaviour      Velocity Analysis
     |                      |
     +----------+-----------+
                |
                v
          Fraud Engine
                |
                v
          Risk Evaluation
                |
                v
       Decision Generation
                |
                v
     APPROVE / REVIEW / DECLINE
                |
                v
       Persist Transaction
       Persist Fraud Result
       Update Customer Profile
```

The fintech remains responsible for its own transaction processing and final transaction execution. RuztIQ provides the fraud evaluation and decisioning layer.

---

## Fraud Detection Engine

The fraud engine combines several categories of signals.

### Transaction Level Signals

The current engine evaluates factors including:

* Transaction amount
* Transaction time
* Merchant category
* Payment method
* Transaction status

Examples of currently implemented rules include:

* High amount transactions
* Late night transactions
* High entertainment spending
* High value USSD transactions
* Failed payments

### Customer Behaviour

Where customer history is available, RuztIQ can evaluate behavioural differences against the customer's known activity.

Current behavioural signals include:

* New device
* New location
* New IP address
* First time merchant
* Spending anomaly
* Repeated failed payments

Customer history is maintained through customer profiles stored in DynamoDB.

### Velocity

RuztIQ supports velocity based evaluation as part of the fraud engine.

Velocity signals can contribute additional risk to a transaction and can produce a velocity violation that is returned with the final decision.

---

## Risk Scoring

The fraud engine calculates a cumulative risk score from the applicable rules and signals.

Current risk levels are:

|   Risk Score | Risk Level |
| -----------: | ---------- |
|      0 to 29 | LOW        |
|     30 to 59 | MEDIUM     |
| 60 and above | HIGH       |

The current fraud threshold is:

```text
50
```

A transaction reaching or exceeding the fraud threshold is marked as fraudulent.

Operational decisions are generated separately from the fraud score so that the system can return both the analytical result and the transaction action.

---

## Decisioning

RuztIQ produces an operational transaction decision based on the fraud evaluation.

The supported decision states are:

```text
APPROVE
REVIEW
DECLINE
```

This allows a fintech to determine how the result should affect its transaction flow.

For example:

```text
LOW RISK
    |
    +--> APPROVE

MEDIUM RISK
    |
    +--> REVIEW

HIGH RISK / FRAUD
    |
    +--> DECLINE
```

The exact thresholds and decision behaviour are configurable within the application logic.

---

## API

The production API is exposed through Amazon API Gateway.

Current endpoint:

```text
POST /Prod/score
```

The deployed API uses an authentication layer before requests reach the fraud detection Lambda.

### Authentication

Requests require a Bearer token:

```http
Authorization: Bearer <token>
```

The expected credential is stored in AWS Secrets Manager.

The API authorizer:

1. Extracts the Bearer token.
2. Retrieves the expected credential from Secrets Manager.
3. Compares the supplied credential using constant time comparison.
4. Returns an API Gateway Allow or Deny policy.

---

## Example Request

```json
{
  "transaction_reference": "RZ-LIVE-20260924-001",
  "customer_id": 1001,
  "amount": 25000.00,
  "currency": "NGN",
  "merchant_id": "MERCHANT-001",
  "merchant_name": "Test Merchant",
  "merchant_category": "RETAIL",
  "device_id": "DEVICE-001",
  "device_type": "MOBILE",
  "location": "Lagos, Nigeria",
  "transaction_time": "2026-09-24T20:00:00+01:00",
  "payment_method": "CARD",
  "ip_address": "197.210.70.10",
  "status": "APPROVED"
}
```

---

## Example Response

```json
{
  "transaction_reference": "RZ-LIVE-20260924-001",
  "risk_score": 0,
  "risk_level": "LOW",
  "is_fraud": false,
  "reasons": "No suspicious activity",
  "decision": "APPROVE",
  "decision_reason": "Transaction is below the configured review threshold.",
  "velocity_violation": false
}
```

---

## High Risk Example

The deployed API was also tested with a high risk transaction containing:

* A ₦200,000 transaction amount
* A late night transaction time
* A failed payment status

RuztIQ returned:

```json
{
  "transaction_reference": "RZ-LIVE-20260924-HIGH-001",
  "risk_score": 65,
  "risk_level": "HIGH",
  "is_fraud": true,
  "reasons": "High Amount, Late Night, Failed Payment",
  "decision": "DECLINE",
  "decision_reason": "Fraud engine identified the transaction as fraudulent.",
  "velocity_violation": false
}
```

The corresponding fraud result was persisted in DynamoDB.

---

## Persistence

The current production architecture uses Amazon DynamoDB.

The primary persistence areas are:

### Transactions

Stores transaction records used by the fraud pipeline and customer history.

### Customer Profiles

Stores customer behavioural information including known:

* Devices
* Locations
* Payment methods
* Merchants
* IP addresses
* Transaction history

### Fraud Results

Stores the result of fraud evaluation together with the decision snapshot.

Persisted decision information includes:

* Decision
* Decision reason
* Decision risk score
* Decision risk level
* Decision fraud status
* Velocity violation
* Fraud reasons
* Evaluation timestamp

This allows the decision returned to the client to be retained as an auditable result.

---

## Duplicate Transaction Protection

RuztIQ protects fraud result persistence against duplicate transaction references.

A repeated request using the same transaction reference does not create an additional fraud result.

This behaviour was verified against the deployed system.

The duplicate transaction test returned the existing decision while the corresponding DynamoDB records remained at:

```text
Fraud results: 1
Customer transactions: 1
```

for the tested transaction.

---

## AWS Architecture

The current deployment uses AWS serverless components.

```text
                    Internet
                       |
                       v
              Amazon API Gateway
                       |
                       v
             Lambda Authorizer
                       |
                       v
             Fraud Detection Lambda
                       |
          +------------+------------+
          |            |            |
          v            v            v
     Fraud Engine   Customer    Transaction
                    Profiles     Processing
          |            |            |
          +------------+------------+
                       |
                       v
                  DynamoDB
          +------------+------------+
          |            |            |
          v            v            v
     Transactions  Customers   Fraud Results
```

Current Lambda runtime:

```text
Python 3.11
```

Fraud detection Lambda configuration includes:

```text
Memory: 256 MB
Timeout: 60 seconds
Runtime: Python 3.11
```

The Lambda is deployed in:

```text
eu-west-1
```

---

## API Security

RuztIQ currently uses:

* API Gateway
* Lambda request authorizer
* AWS Secrets Manager
* HMAC based token comparison
* IAM execution roles
* CloudWatch monitoring

The authorizer retrieves the API credential from Secrets Manager rather than storing the credential directly in source code.

---

## Monitoring

The deployment includes CloudWatch monitoring for the API and fraud detection Lambda.

Configured monitoring includes:

* Lambda errors
* Lambda throttles
* API Gateway 4XX responses
* API Gateway 5XX responses
* API Gateway latency

A production verification check recorded:

```text
Fraud Detection Lambda Errors: 0
Fraud Detection Lambda Throttles: 0
```

during the tested monitoring window.

---

## Testing

The repository contains automated tests covering the fraud detection system, repositories, request routing, validation and related application behaviour.

The current production checkpoint was verified with:

```text
121 passed in 5.61s
```

The repository also passed:

```bash
git diff --check
```

The deployed Lambda functions were confirmed to be in an active state with successful last update status.

---

## Infrastructure Validation

The AWS CloudFormation stack was verified with:

```text
UPDATE_COMPLETE
```

The deployment contains the primary RuztIQ components including:

* API Gateway
* Fraud Detection Lambda
* RuztIQ API Authorizer Lambda
* DynamoDB transaction storage
* DynamoDB customer profile storage
* DynamoDB fraud result storage
* CloudWatch alarms
* Lambda permissions
* IAM roles

---

## Production Integration Model

RuztIQ is designed to integrate with an existing fintech transaction flow rather than replace the fintech's transaction infrastructure.

The intended production model is:

```text
Customer
   |
   v
Fintech Application
   |
   v
Fintech Transaction Service
   |
   v
RuztIQ Fraud Decision API
   |
   +------ APPROVE ------> Continue transaction
   |
   +------ REVIEW -------> Fintech review workflow
   |
   +------ DECLINE ------> Stop transaction
```

The fintech remains the system responsible for executing the transaction.

RuztIQ provides the risk decision required by that transaction flow.

A production integration would normally involve:

1. Mapping the fintech's transaction fields to the RuztIQ request format.
2. Connecting the fintech's transaction service to the RuztIQ API.
3. Defining how APPROVE, REVIEW and DECLINE are handled.
4. Testing the integration in a sandbox environment.
5. Running controlled production traffic.
6. Monitoring latency, errors, decisions and operational behaviour.
7. Expanding coverage after successful validation.

---

## Repository Structure

The repository is organised around the main components of the fraud decisioning pipeline.

```text
ruztiq/
│
├── infrastructure/
│   ├── template.yaml
│   └── samconfig.toml
│
├── src/
│   ├── fraud/
│   │   └── fraud_engine.py
│   │
│   ├── lambda_function/
│   │   ├── handler.py
│   │   └── authorizer.py
│   │
│   ├── models/
│   │
│   ├── profiles/
│   │
│   ├── repositories/
│   │   ├── customer_profile_repository.py
│   │   ├── fraud_repository.py
│   │   └── transaction_repository.py
│   │
│   ├── services/
│   │
│   └── ...
│
├── tests/
│
├── requirements.txt
└── README.md
```

---

## Local Development

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the test suite:

```bash
pytest -q
```

Run a repository integrity check:

```bash
git diff --check
```

---

## AWS Deployment

The infrastructure is defined using AWS SAM.

Validate the template:

```bash
sam validate --lint
```

Build the application:

```bash
sam build
```

Deploy using the configured SAM deployment settings:

```bash
sam deploy
```

AWS credentials and the required deployment configuration must be available in the local environment.

---

## Current Production Checkpoint

The current repository checkpoint is:

```text
Commit:
53fe7cc

Message:
feat: migrate RuztIQ persistence to DynamoDB
```

Production tag:

```text
ruztiq-v1.1-dynamodb-production
```

The checkpoint represents the DynamoDB based production architecture with:

* Live API Gateway endpoint
* Authenticated API access
* Lambda fraud detection
* Lambda request authorizer
* DynamoDB persistence
* Customer profiles
* Fraud result persistence
* Duplicate transaction protection
* CloudWatch monitoring
* Automated test coverage

The production checkpoint was verified with 121 passing automated tests and successful live API transactions.

---

## Technology Stack

| Component      | Technology               |
| -------------- | ------------------------ |
| Application    | Python                   |
| Runtime        | AWS Lambda Python 3.11   |
| API            | Amazon API Gateway       |
| Authentication | Lambda Authorizer        |
| Secrets        | AWS Secrets Manager      |
| Persistence    | Amazon DynamoDB          |
| Infrastructure | AWS SAM / CloudFormation |
| Monitoring     | Amazon CloudWatch        |
| Testing        | Pytest                   |

---

## Design Principles

RuztIQ is built around several principles:

### Real Time Decisioning

Fraud evaluation happens as part of the transaction request rather than relying solely on post transaction analysis.

### Explainable Decisions

The API returns the risk score, risk level, fraud reasons and decision reason alongside the operational decision.

### Behaviour Based Risk

Customer history can contribute to transaction evaluation rather than treating every transaction in isolation.

### Separation of Responsibilities

RuztIQ provides fraud intelligence and decisioning while the fintech remains responsible for its transaction processing infrastructure.

### Serverless Architecture

The current deployment uses managed AWS services to provide a scalable API and event driven application architecture without requiring dedicated application servers.

### Extensibility

The fraud engine is structured around individual rules, thresholds and behavioural signals so that additional detection logic can be introduced as transaction patterns evolve.

---

## Current Status

RuztIQ has moved beyond the initial prototype stage.

The current system has a deployed and authenticated API, a functioning fraud decisioning pipeline, persistent DynamoDB storage, customer behavioural profiles, operational decision output, monitoring and automated test coverage.

The next stage is integration with a real fintech transaction environment.

That integration connects an existing transaction service to the RuztIQ decision API so that RuztIQ can evaluate transactions as they move through the fintech's actual transaction flow.

---

## Project Objective

The long term objective of RuztIQ is to provide fintechs with a dedicated fraud decisioning layer capable of evaluating transactions in real time, learning from customer transaction behaviour and providing consistent, explainable transaction decisions.

The system is designed to become part of the transaction infrastructure rather than simply another dashboard for reviewing fraud after it has happened.

# RuztIQ

## Real Time Fintech Fraud Detection and Transaction Decisioning

RuztIQ is a real time fraud detection and transaction decisioning service designed for fintech transaction environments.

It evaluates incoming transactions using transaction level rules, customer behavioural signals and velocity analysis, then returns an actionable decision:

**APPROVE**, **REVIEW**, or **DECLINE**.

The system is designed to sit at the transaction decision point of a fintech system, allowing the fintech to evaluate risk before completing a transaction.

---

## What RuztIQ Does

RuztIQ receives transaction information through an authenticated API and evaluates the transaction against its configured fraud detection rules and available customer history.

The resulting response contains:

* Transaction reference
* Risk score
* Risk level
* Fraud status
* Fraud reasons
* Operational decision
* Decision reason
* Velocity violation status

A typical decision therefore provides both an outcome and the reasoning behind that outcome.

Example:

```json
{
  "transaction_reference": "RZ-LIVE-20260924-HIGH-001",
  "risk_score": 65,
  "risk_level": "HIGH",
  "is_fraud": true,
  "reasons": "High Amount, Late Night, Failed Payment",
  "decision": "DECLINE",
  "decision_reason": "Fraud engine identified the transaction as fraudulent.",
  "velocity_violation": false
}
```

---

## Core Decision Flow

The current decision flow is:

```text
Transaction
     |
     v
API Gateway
     |
     v
Request Authorizer
     |
     v
RuztIQ Lambda
     |
     v
Request Validation
     |
     v
Transaction Conversion
     |
     v
Fraud Detection Pipeline
     |
     +----------------------+
     |                      |
     v                      v
Customer Behaviour      Velocity Analysis
     |                      |
     +----------+-----------+
                |
                v
          Fraud Engine
                |
                v
          Risk Evaluation
                |
                v
       Decision Generation
                |
                v
     APPROVE / REVIEW / DECLINE
                |
                v
       Persist Transaction
       Persist Fraud Result
       Update Customer Profile
```

The fintech remains responsible for its own transaction processing and final transaction execution. RuztIQ provides the fraud evaluation and decisioning layer.

---

## Fraud Detection Engine

The fraud engine combines several categories of signals.

### Transaction Level Signals

The current engine evaluates factors including:

* Transaction amount
* Transaction time
* Merchant category
* Payment method
* Transaction status

Examples of currently implemented rules include:

* High amount transactions
* Late night transactions
* High entertainment spending
* High value USSD transactions
* Failed payments

### Customer Behaviour

Where customer history is available, RuztIQ can evaluate behavioural differences against the customer's known activity.

Current behavioural signals include:

* New device
* New location
* New IP address
* First time merchant
* Spending anomaly
* Repeated failed payments

Customer history is maintained through customer profiles stored in DynamoDB.

### Velocity

RuztIQ supports velocity based evaluation as part of the fraud engine.

Velocity signals can contribute additional risk to a transaction and can produce a velocity violation that is returned with the final decision.

---

## Risk Scoring

The fraud engine calculates a cumulative risk score from the applicable rules and signals.

Current risk levels are:

|   Risk Score | Risk Level |
| -----------: | ---------- |
|      0 to 29 | LOW        |
|     30 to 59 | MEDIUM     |
| 60 and above | HIGH       |

The current fraud threshold is:

```text
50
```

A transaction reaching or exceeding the fraud threshold is marked as fraudulent.

Operational decisions are generated separately from the fraud score so that the system can return both the analytical result and the transaction action.

---

## Decisioning

RuztIQ produces an operational transaction decision based on the fraud evaluation.

The supported decision states are:

```text
APPROVE
REVIEW
DECLINE
```

This allows a fintech to determine how the result should affect its transaction flow.

For example:

```text
LOW RISK
    |
    +--> APPROVE

MEDIUM RISK
    |
    +--> REVIEW

HIGH RISK / FRAUD
    |
    +--> DECLINE
```

The exact thresholds and decision behaviour are configurable within the application logic.

---

## API

The production API is exposed through Amazon API Gateway.

Current endpoint:

```text
POST /Prod/score
```

The deployed API uses an authentication layer before requests reach the fraud detection Lambda.

### Authentication

Requests require a Bearer token:

```http
Authorization: Bearer <token>
```

The expected credential is stored in AWS Secrets Manager.

The API authorizer:

1. Extracts the Bearer token.
2. Retrieves the expected credential from Secrets Manager.
3. Compares the supplied credential using constant time comparison.
4. Returns an API Gateway Allow or Deny policy.

---

## Example Request

```json
{
  "transaction_reference": "RZ-LIVE-20260924-001",
  "customer_id": 1001,
  "amount": 25000.00,
  "currency": "NGN",
  "merchant_id": "MERCHANT-001",
  "merchant_name": "Test Merchant",
  "merchant_category": "RETAIL",
  "device_id": "DEVICE-001",
  "device_type": "MOBILE",
  "location": "Lagos, Nigeria",
  "transaction_time": "2026-09-24T20:00:00+01:00",
  "payment_method": "CARD",
  "ip_address": "197.210.70.10",
  "status": "APPROVED"
}
```

---

## Example Response

```json
{
  "transaction_reference": "RZ-LIVE-20260924-001",
  "risk_score": 0,
  "risk_level": "LOW",
  "is_fraud": false,
  "reasons": "No suspicious activity",
  "decision": "APPROVE",
  "decision_reason": "Transaction is below the configured review threshold.",
  "velocity_violation": false
}
```

---

## High Risk Example

The deployed API was also tested with a high risk transaction containing:

* A ₦200,000 transaction amount
* A late night transaction time
* A failed payment status

RuztIQ returned:

```json
{
  "transaction_reference": "RZ-LIVE-20260924-HIGH-001",
  "risk_score": 65,
  "risk_level": "HIGH",
  "is_fraud": true,
  "reasons": "High Amount, Late Night, Failed Payment",
  "decision": "DECLINE",
  "decision_reason": "Fraud engine identified the transaction as fraudulent.",
  "velocity_violation": false
}
```

The corresponding fraud result was persisted in DynamoDB.

---

## Persistence

The current production architecture uses Amazon DynamoDB.

The primary persistence areas are:

### Transactions

Stores transaction records used by the fraud pipeline and customer history.

### Customer Profiles

Stores customer behavioural information including known:

* Devices
* Locations
* Payment methods
* Merchants
* IP addresses
* Transaction history

### Fraud Results

Stores the result of fraud evaluation together with the decision snapshot.

Persisted decision information includes:

* Decision
* Decision reason
* Decision risk score
* Decision risk level
* Decision fraud status
* Velocity violation
* Fraud reasons
* Evaluation timestamp

This allows the decision returned to the client to be retained as an auditable result.

---

## Duplicate Transaction Protection

RuztIQ protects fraud result persistence against duplicate transaction references.

A repeated request using the same transaction reference does not create an additional fraud result.

This behaviour was verified against the deployed system.

The duplicate transaction test returned the existing decision while the corresponding DynamoDB records remained at:

```text
Fraud results: 1
Customer transactions: 1
```

for the tested transaction.

---

## AWS Architecture

The current deployment uses AWS serverless components.

```text
                    Internet
                       |
                       v
              Amazon API Gateway
                       |
                       v
             Lambda Authorizer
                       |
                       v
             Fraud Detection Lambda
                       |
          +------------+------------+
          |            |            |
          v            v            v
     Fraud Engine   Customer    Transaction
                    Profiles     Processing
          |            |            |
          +------------+------------+
                       |
                       v
                  DynamoDB
          +------------+------------+
          |            |            |
          v            v            v
     Transactions  Customers   Fraud Results
```

Current Lambda runtime:

```text
Python 3.11
```

Fraud detection Lambda configuration includes:

```text
Memory: 256 MB
Timeout: 60 seconds
Runtime: Python 3.11
```

The Lambda is deployed in:

```text
eu-west-1
```

---

## API Security

RuztIQ currently uses:

* API Gateway
* Lambda request authorizer
* AWS Secrets Manager
* HMAC based token comparison
* IAM execution roles
* CloudWatch monitoring

The authorizer retrieves the API credential from Secrets Manager rather than storing the credential directly in source code.

---

## Monitoring

The deployment includes CloudWatch monitoring for the API and fraud detection Lambda.

Configured monitoring includes:

* Lambda errors
* Lambda throttles
* API Gateway 4XX responses
* API Gateway 5XX responses
* API Gateway latency

A production verification check recorded:

```text
Fraud Detection Lambda Errors: 0
Fraud Detection Lambda Throttles: 0
```

during the tested monitoring window.

---

## Testing

The repository contains automated tests covering the fraud detection system, repositories, request routing, validation and related application behaviour.

The current production checkpoint was verified with:

```text
121 passed in 5.61s
```

The repository also passed:

```bash
git diff --check
```

The deployed Lambda functions were confirmed to be in an active state with successful last update status.

---

## Infrastructure Validation

The AWS CloudFormation stack was verified with:

```text
UPDATE_COMPLETE
```

The deployment contains the primary RuztIQ components including:

* API Gateway
* Fraud Detection Lambda
* RuztIQ API Authorizer Lambda
* DynamoDB transaction storage
* DynamoDB customer profile storage
* DynamoDB fraud result storage
* CloudWatch alarms
* Lambda permissions
* IAM roles

---

## Production Integration Model

RuztIQ is designed to integrate with an existing fintech transaction flow rather than replace the fintech's transaction infrastructure.

The intended production model is:

```text
Customer
   |
   v
Fintech Application
   |
   v
Fintech Transaction Service
   |
   v
RuztIQ Fraud Decision API
   |
   +------ APPROVE ------> Continue transaction
   |
   +------ REVIEW -------> Fintech review workflow
   |
   +------ DECLINE ------> Stop transaction
```

The fintech remains the system responsible for executing the transaction.

RuztIQ provides the risk decision required by that transaction flow.

A production integration would normally involve:

1. Mapping the fintech's transaction fields to the RuztIQ request format.
2. Connecting the fintech's transaction service to the RuztIQ API.
3. Defining how APPROVE, REVIEW and DECLINE are handled.
4. Testing the integration in a sandbox environment.
5. Running controlled production traffic.
6. Monitoring latency, errors, decisions and operational behaviour.
7. Expanding coverage after successful validation.

---

## Repository Structure

The repository is organised around the main components of the fraud decisioning pipeline.

```text
ruztiq/
│
├── infrastructure/
│   ├── template.yaml
│   └── samconfig.toml
│
├── src/
│   ├── fraud/
│   │   └── fraud_engine.py
│   │
│   ├── lambda_function/
│   │   ├── handler.py
│   │   └── authorizer.py
│   │
│   ├── models/
│   │
│   ├── profiles/
│   │
│   ├── repositories/
│   │   ├── customer_profile_repository.py
│   │   ├── fraud_repository.py
│   │   └── transaction_repository.py
│   │
│   ├── services/
│   │
│   └── ...
│
├── tests/
│
├── requirements.txt
└── README.md
```

---

## Local Development

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the test suite:

```bash
pytest -q
```

Run a repository integrity check:

```bash
git diff --check
```

---

## AWS Deployment

The infrastructure is defined using AWS SAM.

Validate the template:

```bash
sam validate --lint
```

Build the application:

```bash
sam build
```

Deploy using the configured SAM deployment settings:

```bash
sam deploy
```

AWS credentials and the required deployment configuration must be available in the local environment.

---

## Current Production Checkpoint

The current repository checkpoint is:

```text
Commit:
53fe7cc

Message:
feat: migrate RuztIQ persistence to DynamoDB
```

Production tag:

```text
ruztiq-v1.1-dynamodb-production
```

The checkpoint represents the DynamoDB based production architecture with:

* Live API Gateway endpoint
* Authenticated API access
* Lambda fraud detection
* Lambda request authorizer
* DynamoDB persistence
* Customer profiles
* Fraud result persistence
* Duplicate transaction protection
* CloudWatch monitoring
* Automated test coverage

The production checkpoint was verified with 121 passing automated tests and successful live API transactions.

---

## Technology Stack

| Component      | Technology               |
| -------------- | ------------------------ |
| Application    | Python                   |
| Runtime        | AWS Lambda Python 3.11   |
| API            | Amazon API Gateway       |
| Authentication | Lambda Authorizer        |
| Secrets        | AWS Secrets Manager      |
| Persistence    | Amazon DynamoDB          |
| Infrastructure | AWS SAM / CloudFormation |
| Monitoring     | Amazon CloudWatch        |
| Testing        | Pytest                   |

---

## Design Principles

RuztIQ is built around several principles:

### Real Time Decisioning

Fraud evaluation happens as part of the transaction request rather than relying solely on post transaction analysis.

### Explainable Decisions

The API returns the risk score, risk level, fraud reasons and decision reason alongside the operational decision.

### Behaviour Based Risk

Customer history can contribute to transaction evaluation rather than treating every transaction in isolation.

### Separation of Responsibilities

RuztIQ provides fraud intelligence and decisioning while the fintech remains responsible for its transaction processing infrastructure.

### Serverless Architecture

The current deployment uses managed AWS services to provide a scalable API and event driven application architecture without requiring dedicated application servers.

### Extensibility

The fraud engine is structured around individual rules, thresholds and behavioural signals so that additional detection logic can be introduced as transaction patterns evolve.

---

## Current Status

RuztIQ has moved beyond the initial prototype stage.

The current system has a deployed and authenticated API, a functioning fraud decisioning pipeline, persistent DynamoDB storage, customer behavioural profiles, operational decision output, monitoring and automated test coverage.

The next stage is integration with a real fintech transaction environment.

That integration connects an existing transaction service to the RuztIQ decision API so that RuztIQ can evaluate transactions as they move through the fintech's actual transaction flow.

---

## Project Objective

The long term objective of RuztIQ is to provide fintechs with a dedicated fraud decisioning layer capable of evaluating transactions in real time, learning from customer transaction behaviour and providing consistent, explainable transaction decisions.

The system is designed to become part of the transaction infrastructure rather than simply another dashboard for reviewing fraud after it has happened.
