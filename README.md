# 🚀 SyncKar
### Event-Driven Interoperability Layer for Karnataka Single Window System

> Two-way synchronization. Zero legacy modifications. BSA 2023 compliant audit trails.

![Kafka](https://img.shields.io/badge/Apache-Kafka-black)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-green)
![Redis](https://img.shields.io/badge/Redis-Idempotency-red)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-Audit-blue)
![AWS](https://img.shields.io/badge/AWS-Cloud-orange)

🏆 AI4Bharat Government Tech Innovation Project  
⚡ Real-time Sync Across 40+ Department Systems  
🔐 Court-Admissible Digital Audit Trails  
🧠 AI-Assisted Schema Mapping

SyncKar is a middleware layer that synchronizes state bidirectionally between the Karnataka Single Window System (SWS) and 40+ legacy department systems. The system strictly adheres to a "Leave and Layer" architecture: no modifications to source systems or their databases are permitted. 

## The Problem

Karnataka's e-governance infrastructure contains 40+ isolated legacy systems operating in parallel with the forward-looking Single Window System (SWS). A single-day cutover is not viable. 

Currently, an update to a business record (e.g., registered address) in SWS does not propagate to the Factories or Trade License systems, and vice versa. This split-brain architecture results in:
* 4M–8M redundant form submissions annually by 2M+ businesses.
* Unsynchronized state causing outdated field inspections and compliance notices.
* No shared clock across 40+ endpoints, making timestamp-based conflict resolution impossible.
* Legacy systems lacking event emission capabilities (no webhooks or message queues).

## 🏛️ Why SyncKar?

SyncKar implements a decentralized, protocol-agnostic propagation mechanism using the Unique Business Identifier (UBID) as the sole join key. If a record lacks a UBID, it is invisible to the sync layer by design. No heuristic matching or scoring is used.

SyncKar guarantees strict per-business event ordering, mathematical idempotency against network retries, and automated conflict resolution without human intervention for 95% of collisions.

## Architecture Walkthrough

SyncKar connects unmodified source systems via a central Kafka event bus.

<img width="1600" height="833" alt="synckar arch" src="https://github.com/user-attachments/assets/dc3be81c-caba-4e51-975c-53baa8c03bb6" />
<img width="1258" height="868" alt="synckar aws arch" src="https://github.com/user-attachments/assets/53925844-6334-4089-b3ba-946952c08e15" />

### 1. Ingress and Egress Paths
* **SWS → Departments:** Webhook-driven. Changes are written to a PostgreSQL Transactional Outbox, published to Kafka (`sws.changes`), and consumed by department-specific adapters.
* **Departments → SWS:** Pull-driven. Adapters perform stateful API polling (maintaining high-water marks) or cryptographic snapshot diffing (MurmurHash3) to detect legacy system mutations, translating them into canonical JSON events.

### 2. Schema Translation & Drift Detection
Adapters process Git-versioned mapping files (YAML/JSON) to convert canonical payloads into SOAP/XML, REST, or CSV formats. A data observability module runs on the ingress path to flag structural anomalies (e.g., column renamed) or statistical drift (e.g., sudden null-rate spikes). Affected records enter a quarantine topic until the mapping version is updated.

### 3. Deterministic Idempotency Engine
To prevent duplicate writes on network failure, adapters compute a time-independent hash:
`IdempotencyKey = SHA-256(source_system_id + source_event_id + UBID + field_name + new_value)`
Write operations execute via a Two-Phase Reservation pattern in Redis (`SET NX`). If an adapter crashes post-write but pre-ACK, the Redis key (`COMPLETED`) forces the adapter to drop the Kafka retry.

### 4. Automated Conflict Resolution
Timestamp-based resolution fails across legacy systems. SyncKar uses Kafka offset sequence numbers for temporal ordering. If overlapping mutations for the same UBID and field occur within a configurable sliding window, a deterministic policy matrix applies:
* **Source Priority:** SWS wins on universal demographics (e.g., Registered Address).
* **Domain Priority:** Departments win on regulatory compliance fields (e.g., License Status).
* **Broker Sequence:** Last-write-wins on unrestricted metadata based on Kafka offsets.
The losing payload is logged in the audit trail, ensuring zero silent overwrites.

## ✨ Core Features

### ⚡ Event Broker and Outbox Pattern
Redpanda (Kafka-compatible API) topics are partitioned by UBID to enforce strict ordering. The PostgreSQL Outbox guarantees event publication even during network partitions between the middleware and the broker.

### 🔐 BSA 2023 Compliant Audit Ledger
Fulfills Section 63(4) of the Bharatiya Sakshya Adhiniyam, 2023. Every transaction generates an append-only PostgreSQL row containing the `correlation_id`, old/new state, and resolution policy applied. Each row is individually hashed via SHA-256 and signed with an RSA private key.

### 🧠 Privacy-Preserving AI Schema Co-Pilot
Hosted LLMs accelerate the onboarding of new departments by drafting schema mappings. LLMs process only schema headers and DPDP-compliant synthetic data generated via an on-premises Synthetic Data Vault (SDV). A government architect certifies the draft before deployment.

### 🔥 Failure Modes and Circuit Breakers
Department API latency variances are managed via per-adapter throttling (Kafka consumer group backpressure). Persistent legacy API failures trigger an `OPEN` circuit breaker state, pausing processing to prevent thundering-herd retry storms.

## 📊 System Metrics & Throughput

| Metric | Target Specification |
|---|---|
| Sustained Event Rate | ~15–25 events/second |
| Peak Write Throughput | ~2500–5000 API calls/second (batch spikes) |
| Latency Profile | Near-real-time (webhooks); 30s–15min (polling) |
| Conflict Resolution | Automated (95%); DLQ routing for unknowns (5%) |
| Storage Profile | ~500GB/year for 2M businesses × 40 depts |
| Code Coverage | 80% statement coverage |

## 📸 Screenshots
<img width="1600" height="771" alt="liv pro 1" src="https://github.com/user-attachments/assets/21828197-388f-4c2a-bcdf-5c7fd44f5182" />
<img width="1600" height="776" alt="liv pro 2" src="https://github.com/user-attachments/assets/66147631-356d-4091-b4c3-f279a11f5545" />
<img width="1600" height="772" alt="liv pro 3" src="https://github.com/user-attachments/assets/907f32e7-5729-4266-9dab-59260b12a1e6" />
<img width="1600" height="768" alt="liv pro 4" src="https://github.com/user-attachments/assets/208d2fa4-f64f-4c76-b9ea-bf7466013d0a" />
<img width="1600" height="777" alt="liv pro 5" src="https://github.com/user-attachments/assets/f29267ba-9366-4eb0-a966-fa0715dd5602" />
<img width="1600" height="778" alt="liv pro 6" src="https://github.com/user-attachments/assets/42d52b8d-d5ce-4e21-965d-4687c79270bc" />
<img width="1600" height="815" alt="liv pro 7" src="https://github.com/user-attachments/assets/05ddb7f9-308a-41a6-967d-b2fc4fcdf6cb" />
<img width="1600" height="772" alt="liv pro 8" src="https://github.com/user-attachments/assets/061fd101-e756-4420-9d07-264df126333b" />

## Project Structure

* `synckar/synckar/`: FastAPI backend adapters, Redis idempotency logic, and Kafka consumers/producers.
* `synckar/mock_systems/`: Containerized endpoints mimicking SWS, Shop Establishment (SOAP), and Factories (REST).
* `synckar/dashboard/`: React SPA. Functions as the Data Steward interface for DLQ review and audit searches.
* `synckar/tests/`: Integration tests simulating dual-write conflicts, network partitions, and DB migrations.

## 💻 Instructions to Run & Test

Deployment relies on Docker and Docker Compose. All required infrastructure (Redpanda, PostgreSQL, Redis) and mock department endpoints are containerized.

### 1. Local Environment Setup
```bash
cd synckar
cp .env.example .env
```

### 2. Bootstrapping Infrastructure
Start the core services and wait for the API to report a healthy status:
```bash
docker compose up --build -d

# Verify connectivity
curl http://localhost:18080/health
```

### 3. Database Initialization
Execute the schema migrations to configure the PostgreSQL outbox and audit ledgers, then seed the mock systems with initial state:
```bash
docker compose exec synckar-api python scripts/run_migrations.py
docker compose exec synckar-api python scripts/seed_data.py
```

### 4. Executing Demo Scenarios
The repository includes automated scripts that inject mutations to verify bidirectional propagation and conflict resolution.

* **Scenario A (SWS → Departments):** 
  ```bash
  docker compose exec synckar-api python scripts/demo_scenario_a.py
  ```
  *Action:* Updates business address in SWS.
  *Expected:* Propagates to mock Shop Establishment and mock Factories endpoints.

* **Scenario B (Department → SWS):**
  ```bash
  docker compose exec synckar-api python scripts/demo_scenario_b.py
  ```
  *Action:* Emulates a factory status change.
  *Expected:* Propagates upward to SWS via pull-based polling.

* **Scenario C (Conflict Matrix):**
  ```bash
  docker compose exec synckar-api python scripts/demo_scenario_c.py
  ```
  *Action:* Fires simultaneous updates to the same UBID.
  *Expected:* Deterministic resolution without silent overwrites.

### 5. Accessing the Dashboard
Open the React-based Data Steward interface to view the Dead Letter Queue (DLQ) and trace audit ledgers:
* **URL:** `http://localhost:18080/dashboard`

## 🧪 Test Coverage and Verification

SyncKar executes a robust suite testing idempotency, backoff algorithms, and ledger append consistency. The test suite sits at an exact **80% statement coverage** threshold (`coverage.json`).

To run the full suite:
```bash
docker compose exec synckar-api pytest tests/ -v
```

Expected output:
```text
[INFO] Starting SyncKar full test suite on local environment
[INFO] PART 1: Connectivity Tests
[PASS] SWS Health: http://localhost:8000/health
[PASS] Shop Health: http://localhost:8001/health
[PASS] SyncKar Health: http://localhost:18080/health
[INFO] PART 4: Flow Test A: SWS to Departments Propagation
[PASS] Shop Establishment propagation successful after 5s
[INFO] PART 5: Flow Test B: Department to SWS Propagation
[PASS] SWS propagation successful after 10s
[INFO] PART 6: Audit Trail Tests
[PASS] Audit entries have correlation_id field
[PASS] Audit entries have RSA signatures
[INFO] PART 7: Dead Letter Queue Tests
[PASS] DLQ is empty with no unresolved issues
=========================================
All tests passed! (25/25)
```

## 🎥 Live Demo

[▶️ Watch Demo](https://drive.google.com/file/d/1rN8x52SEZiRdaWp-g_cgM12UWZjaP2YT/view?usp=drivesdk)

## 🛡️ Resilience Configuration

* **Exponential Backoff:** Configured on all external HTTP requests (1s → 2s → 4s → max 30min).
* **Circuit Breaker:** Transitions to `OPEN` after 5 consecutive 5xx errors; pings every 60s in `HALF-OPEN`.
* **DLQ Routing:** Unparseable payloads or maximum retry exhaustions are parked in PostgreSQL for Data Steward review.
* **Nightly Reconciliation Job:** Compares random 1% samples of UBID records across endpoints to detect silent drift out-of-band.

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend Framework | Python FastAPI, Celery |
| Event Broker | Redpanda (Kafka Protocol, Partitioned per UBID) |
| Transactional DB | PostgreSQL 16 (Append-only Ledger) |
| State/Lock Store | Redis 7 (Two-Phase Reservation) |
| Frontend Admin | React.js |
| Mock Infrastructure | Docker, Docker Compose |

## 🌍 Public Sector Impact

* Establishes court-admissible electronic records across state endpoints.
* Enables non-invasive ingestion of 40+ independent technical stacks.
* Quantifiable reduction of verification overhead for field officers working from stale datastores.
