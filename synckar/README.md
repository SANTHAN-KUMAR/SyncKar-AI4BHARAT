# SyncKar — Interoperability Layer

**SyncKar** is a non-invasive, event-driven interoperability layer that synchronises Karnataka's Single Window System (SWS) and 40+ legacy department systems **bidirectionally**, without modifying either side.

## Problem

Karnataka's Single Window System (SWS) handles new business registrations, while 40+ legacy department systems continue to accept service requests independently. This creates a **split-brain problem** where the same business data can be updated in multiple systems simultaneously, leading to conflicting records, silent data loss, and regulatory compliance gaps.

## Solution

SyncKar sits **between** SWS and department systems as an interoperability layer:

```
┌─────┐       ┌──────────┐       ┌──────────────┐
│ SWS │◄─────►│ SyncKar  │◄─────►│ 40+ Depts    │
│     │       │ (IL)     │       │ (Legacy APIs)│
└─────┘       └──────────┘       └──────────────┘
```

### Key Features
- **Bidirectional sync** — changes flow SWS↔Departments via Kafka event bus
- **Conflict resolution** — deterministic Policy Matrix (SWS_WINS, DEPT_WINS, LWW, DLQ)
- **BSA 2023 compliant audit** — every record RSA-signed, SHA-256 hashed, append-only
- **Idempotent writes** — Redis Two-Phase Reservation (time-independent keys)
- **Circuit breakers** — per-adapter resilience with automatic recovery
- **Schema translation** — versioned YAML mappings with human certification

## Quick Start (Local)

```bash
# 1. Clone and setup
cd synckar
cp .env.example .env

# 2. Generate RSA keys for audit signing
python scripts/generate_rsa_keys.py

# 3. Start all services (Postgres, Redis, Redpanda, mock systems, API)
docker compose up --build

# 4. Seed test data
python scripts/seed_data.py

# 5. Run demo scenarios
python scripts/demo_scenario_a.py   # SWS → Departments
python scripts/demo_scenario_b.py   # Department → SWS  
python scripts/demo_scenario_c.py   # Conflict resolution
```

## Architecture

```
Polling → Translate → Outbox → Kafka → Consume → Conflict Check
→ Idempotency → Translate Outbound → Write Target → Audit Log
```

### Interactive Architecture Proofs
We have built interactive HTML visualizations to prove the architectural decoupling of the system. These can be opened in any web browser and demonstrate the containerized deployment model:
- **[Live Deployment Proof](architecture-demo.html)**: Interactive visualization of the 5-container Docker Compose architecture on AWS. Proves network isolation and event-driven data flow.
- **[System Architecture](../synckar_architecture.html)**: High-level system design and policy matrix visualization.

### Technology Stack
- **Runtime**: Python 3.11+, FastAPI, Celery
- **Event Bus**: Apache Kafka (KRaft, per-UBID partitioning)
- **Database**: PostgreSQL 16 (Outbox, Audit Ledger)
- **Cache**: Redis 7 (Idempotency, Conflict Window, Circuit Breaker)
- **Dashboard**: React (Vite)

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | System health check |
| `/api/stats` | GET | Dashboard statistics |
| `/api/audit?ubid={ubid}` | GET | Search audit by UBID |
| `/api/audit/trace/{correlation_id}` | GET | End-to-end trace |
| `/api/audit/verify/{audit_id}` | GET | RSA signature verification |
| `/api/dlq` | GET | List DLQ items |
| `/api/dlq/{id}/resolve` | POST | Resolve DLQ item |
| `/api/dlq/conflicts` | GET | List conflict records |
| `/api/webhooks/{system_id}` | POST | Webhook receiver |

## AWS EC2 Deployment

All five services run on a **single EC2 t3.small instance** in one Docker Compose stack. No managed services, no split deployments — one machine, one command.

### Prerequisites (one-time)

1. An EC2 t3.small (or larger) instance running Ubuntu 22.04+
2. Docker + Docker Compose plugin installed on the instance
3. Your PEM key file ready locally
4. EC2 security group with inbound rules:
   - Port **22** (SSH) — your IP
   - Port **18080** (dashboard/API) — 0.0.0.0/0

**Open port 18080 via AWS CLI** (if not already open):
```bash
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxx \
  --protocol tcp --port 18080 --cidr 0.0.0.0/0
```

### Deploy in 3 steps

**Step 1 — SSH into the instance:**
```bash
chmod 400 hackathon_key.pem
ssh -i hackathon_key.pem ubuntu@<EC2_PUBLIC_IP>
```

**Step 2 — Upload the deployment files** (from your local machine, in a separate terminal):
```bash
# Upload the setup script and env template
scp -i hackathon_key.pem synckar/setup.sh ubuntu@<EC2_PUBLIC_IP>:~/setup.sh
```

Or create `setup.sh` directly on the instance — it's committed to the repo and will be available after the first `git clone` inside the script.

**Step 3 — Run the setup script on the instance:**
```bash
bash ~/setup.sh
```

The script will:
- Clone the repo from GitHub
- Copy `.env.ec2` → `.env` (all URLs pre-configured for Docker internal DNS)
- Run `docker compose up --build -d` with EC2 overrides
- Wait for the API health check to pass
- Run database migrations and seed demo data
- Print the dashboard URL

**Expected time:** 3–8 minutes (mostly Docker image build on first run).

### Optional: inject your RSA key

For consistent audit signatures across restarts, inject your existing RSA key:
```bash
# On the EC2 instance, after setup.sh completes
echo "RSA_PRIVATE_KEY_BASE64=$(base64 -w 0 ~/SyncKar-AI4BHARAT/synckar/keys/private.pem)" \
  >> ~/SyncKar-AI4BHARAT/synckar/.env

cd ~/SyncKar-AI4BHARAT/synckar
docker compose restart synckar-api
```

If you skip this, the container auto-generates a fresh key at build time — fine for a demo.

### Verify the deployment

```bash
# All 5 containers running
docker compose -f docker-compose.yml -f docker-compose.override.yml ps

# API health
curl http://localhost:18080/health

# Open in browser
http://<EC2_PUBLIC_IP>:18080/dashboard
```

### Redeploy after code changes

```bash
cd ~/SyncKar-AI4BHARAT/synckar
git pull
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d
docker compose exec synckar-api python scripts/run_migrations.py
```

### Run demo scenarios on EC2

```bash
cd ~/SyncKar-AI4BHARAT/synckar

# Scenario A: SWS → Departments
docker compose exec synckar-api python scripts/demo_scenario_a.py

# Scenario B: Department → SWS
docker compose exec synckar-api python scripts/demo_scenario_b.py

# Scenario C: Conflict resolution
docker compose exec synckar-api python scripts/demo_scenario_c.py

# Reset between demos
docker compose exec synckar-api python scripts/reset_state.py
docker compose exec synckar-api python scripts/seed_data.py
```

---

## Deployment (legacy — managed services, pre-AWS)

## Demo Scenarios

1. **Scenario A**: Address change in SWS → propagated to Shop Est + Factories
2. **Scenario B**: Signatory change in Factories → propagated to SWS
3. **Scenario C**: Simultaneous updates → conflict detected → SWS_WINS policy applied → both values in audit

## License

Hackathon prototype — Karnataka Commerce & Industries
