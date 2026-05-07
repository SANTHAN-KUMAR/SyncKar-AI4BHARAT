# SyncKar: Event-Driven Interoperability Layer

SyncKar is a production-grade, event-driven interoperability middleware designed to solve the "split-brain" data synchronization challenge between the Karnataka Single Window System (SWS) and its 40+ legacy department systems. It enables real-time, bidirectional state propagation while strictly adhering to the constraint of zero modifications to any source system.

---

## 1. Context and Problem Statement

Karnataka's Single Window System (SWS) is the state's canonical front door for new business registrations and cross-department service requests. However, 40+ legacy department systems remain live and act as the authoritative record for businesses already on their books. 

Because a single-day, big-bang migration from legacy systems to SWS is unviable at this scale, a **split-brain problem** emerges:
* A business can raise a service request (e.g., change of registered address) on either SWS or a specific department portal.
* Currently, an update on one side does not automatically propagate to the other.
* Citizens repeat paperwork, officers conduct inspections based on stale data, and compliance records fall out of sync.

**The Objective:** Design a layer that propagates service requests bidirectionally between SWS and legacy systems using the Unique Business Identifier (UBID) as the common join key, without altering the underlying systems.

---

## 2. Capabilities and Highlights

SyncKar provides an incremental, non-invasive integration layer that operates seamlessly across heterogeneous APIs, webhooks, and polling surfaces.

### Direction 1: SWS to Department Systems
* **Canonical Translation:** Captures service requests raised in SWS and translates the payload into the specific schema and protocol (REST, SOAP, etc.) required by each target department system.
* **UBID Routing:** Routes updates to departments where the business exists based on the Unique Business Identifier.

### Direction 2: Department Systems to SWS
* **Non-Invasive Discovery:** For legacy systems that do not natively emit events, SyncKar utilizes stateful API polling and cryptographic snapshot diffing to independently discover state changes.
* **Upstream Synchronization:** Translates discovered changes from department-specific formats back into the canonical SWS representation and updates the central SWS portal.

---

## 3. Architecture Overview

SyncKar operates as a central event bus utilizing Apache Kafka, PostgreSQL, and Redis to guarantee message ordering, idempotency, and auditability.

![SyncKar Architecture Flow](./assets/synckar_architecture_flow.png)
*(Note: Please ensure the architecture flow image is placed at `assets/synckar_architecture_flow.png`)*

### Core Components
1. **Event Broker (Apache Kafka):** Serves as the partitioned log ensuring ordered, at-least-once delivery of synchronization events.
2. **Idempotency Engine (Redis):** Implements a Two-Phase Reservation pattern to ensure retried network calls do not result in duplicate writes to fragile legacy endpoints.
3. **Audit Ledger (PostgreSQL):** A BSA 2023 compliant, append-only ledger that cryptographically hashes and signs every transaction.
4. **Schema Registry:** Stores declarative mapping files used to translate department-specific schemas into a canonical JSON format.

![AWS Deployment Architecture](./assets/aws_deployment_architecture.png)
*(Note: Please ensure the deployment architecture image is placed at `assets/aws_deployment_architecture.png`)*

---

## 4. Cross-Cutting Concerns Handled

SyncKar is designed to handle distributed system failures elegantly.

* **Automated Conflict Resolution:** When simultaneous updates for the same UBID arrive from different sources within a configurable time window, a sliding-window matrix applies deterministic rules (e.g., *Last-Write-Wins* or *Domain-Priority*).
* **No Silent Overwrites:** The losing value in a conflict is never deleted; it is preserved in the audit log, ensuring every resolution remains explainable and reversible.
* **Deterministic Idempotency:** Time-independent, SHA-256 based keys guarantee that network retries never produce duplicate business events.

---

## 5. Non-Negotiables Met

* **Zero Source System Modifications:** Integrates purely via existing schemas and APIs.
* **UBID as a Precondition:** Relies strictly on the existing UBID as the join key without attempting to match or infer records where it is absent.
* **No Raw PII to Hosted LLMs:** AI is utilized exclusively for generating draft schema mappings using synthetic data; raw citizen data never leaves the secure perimeter.
* **Complete Auditability:** Meets the strict evidentiary requirements of the Bharatiya Sakshya Adhiniyam (BSA) 2023.

---

## 6. Interactive 3D Visualizations

> **Can I run the interactive HTML files directly in this README?**
> Standard Markdown rendering on platforms like GitHub does not support executing raw HTML containing JavaScript and CSS for security reasons. 

To view the interactive, professional 3D visualizations of the system architecture:
1. **Local Viewing:** Clone this repository and open `aws_infrastructure_3d.html` or `synckar_3d_flow.html` directly in any modern web browser.
2. **Live Hosting (Recommended):** Host the HTML files via GitHub Pages or Vercel to allow reviewers to interact with the animations via a public link.

---

## 7. Instructions to Run

The deployment relies on Docker and Docker Compose to orchestrate the core services, mock department APIs, and databases.

### Prerequisites
* Docker
* Docker Compose plugin

### Local Deployment

1. Navigate to the `synckar` directory:
   ```bash
   cd synckar
   ```

2. Copy the environment variables template:
   ```bash
   cp .env.example .env
   ```

3. Build and start the container stack:
   ```bash
   docker compose up --build -d
   ```

4. Verify the API health status:
   ```bash
   curl http://localhost:18080/health
   ```

5. Execute database migrations to prepare the audit ledger:
   ```bash
   docker compose exec synckar-api python scripts/run_migrations.py
   ```

6. Seed the system with initial mock data:
   ```bash
   docker compose exec synckar-api python scripts/seed_data.py
   ```

### Executing Demo Scenarios

The repository includes predefined scripts to simulate real-world data synchronization events:

* **Scenario A (SWS to Departments):**
  ```bash
  docker compose exec synckar-api python scripts/demo_scenario_a.py
  ```

* **Scenario B (Department to SWS):**
  ```bash
  docker compose exec synckar-api python scripts/demo_scenario_b.py
  ```

* **Scenario C (Conflict Resolution):**
  ```bash
  docker compose exec synckar-api python scripts/demo_scenario_c.py
  ```

To reset the database state between scenarios:
```bash
docker compose exec synckar-api python scripts/reset_state.py
docker compose exec synckar-api python scripts/seed_data.py
```

### Accessing the Dashboard

Once the stack is operational, the Data Steward dashboard is accessible at:
`http://localhost:18080/dashboard`

---

## 8. Test Coverage and Verification

SyncKar is designed for production reliability, maintaining 80% statement coverage across all core interoperability modules.

To execute the test suite:
```bash
cd synckar
pytest tests/
```

The test suite systematically verifies connectivity, bidirectional data propagation, circuit breaker health, and audit trail integrity.