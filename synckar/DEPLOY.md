# SyncKar — Cloud Deployment Guide

The dashboard is served from the FastAPI app at `/dashboard` — no separate hosting needed.

---

## Option A — Railway (recommended for hackathon)

Railway gives you a free-tier Postgres and Redis plugin, and deploys straight from GitHub.

### 1. Prerequisites

- GitHub repo with this code pushed
- [Railway account](https://railway.app) (free tier is fine)
- Kafka: sign up for [Aiven](https://aiven.io) free tier (Kafka) — takes ~2 min

### 2. Create the project

```bash
# Install Railway CLI
npm install -g @railway/cli
railway login
railway init   # creates a new project
```

### 3. Add managed services

In the Railway dashboard for your project:
- Click **+ New** → **Database** → **PostgreSQL** — Railway injects `DATABASE_URL` automatically
- Click **+ New** → **Database** → **Redis** — Railway injects `REDIS_URL` automatically

### 4. Deploy the main API

```bash
# From the synckar/ directory
railway up --service synckar-api
```

Railway reads `railway.toml` and builds the Dockerfile (which also builds the React dashboard).

### 5. Deploy Celery worker and beat

In the Railway dashboard, create two more services from the **same repo**:

| Service name         | Start command |
|----------------------|---------------|
| `synckar-worker`     | `celery -A synckar.workers.celery_app worker --loglevel=info --concurrency=2` |
| `synckar-beat`       | `celery -A synckar.workers.celery_app beat --loglevel=info` |

Both use the same Dockerfile. Set the same env vars as the API service.

### 6. Deploy mock systems

Create three more services, each pointing to its own Dockerfile:

| Service name              | Dockerfile path                              |
|---------------------------|----------------------------------------------|
| `synckar-mock-sws`        | `mock_systems/mock_sws/Dockerfile`           |
| `synckar-mock-shop`       | `mock_systems/mock_dept_shop/Dockerfile`     |
| `synckar-mock-factories`  | `mock_systems/mock_dept_factories/Dockerfile`|

### 7. Set environment variables

In the Railway dashboard → your API service → **Variables**, add:

```
KAFKA_BOOTSTRAP_SERVERS=<from-aiven>
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
KAFKA_SASL_USERNAME=<from-aiven>
KAFKA_SASL_PASSWORD=<from-aiven>
KAFKA_SSL_CA_PATH=/app/ca.pem

MOCK_SWS_BASE_URL=https://<synckar-mock-sws>.up.railway.app
MOCK_SHOP_BASE_URL=https://<synckar-mock-shop>.up.railway.app
MOCK_FACTORIES_BASE_URL=https://<synckar-mock-factories>.up.railway.app

RSA_PRIVATE_KEY_BASE64=<base64 of keys/private.pem — see below>
CELERY_BROKER_URL=${{Redis.REDIS_URL}}   # Railway variable reference
CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}
```

Copy the same Kafka + mock URL vars to the worker and beat services.

### 8. Generate RSA_PRIVATE_KEY_BASE64

```bash
# From the synckar/ directory
python scripts/generate_rsa_keys.py   # creates keys/private.pem if missing
base64 -w 0 keys/private.pem          # copy this output into Railway
```

### 9. Upload Aiven CA certificate

Aiven requires an SSL CA cert. Download `ca.pem` from the Aiven console and add it to your Railway service:

```bash
# Option: encode it as a base64 env var and decode at startup
# Or: add it to the Docker image (not recommended for secrets)
```

For the hackathon demo, the simplest approach is to set `KAFKA_SECURITY_PROTOCOL=PLAINTEXT` and use a local Kafka or Upstash Kafka (which doesn't need a CA cert).

### 10. Run the DB migration

After the API service is deployed:

```bash
railway run --service synckar-api -- python -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
with open('migrations/init.sql') as f:
    conn.cursor().execute(f.read())
conn.commit()
print('Migration complete')
"
```

### 11. Seed demo data

```bash
railway run --service synckar-api -- python scripts/seed_data.py
```

### 12. Access the dashboard

```
https://<synckar-api>.up.railway.app/dashboard
```

---

## Option B — Render

Render has a `render.yaml` blueprint already configured.

### 1. Connect repo

- Go to [render.com](https://render.com) → **New** → **Blueprint**
- Connect your GitHub repo and point to `synckar/render.yaml`
- Render will create all services automatically

### 2. Add managed databases

In the Render dashboard, create:
- **PostgreSQL** (free tier) — copy the connection string to `DATABASE_URL`
- **Redis** (free tier) — copy the URL to `REDIS_URL` and `CELERY_BROKER_URL`

### 3. Set secret env vars

For each service, add the same Kafka and RSA vars as described in the Railway section above.

> **Note:** Render free-tier services sleep after 15 minutes of inactivity. For a live demo, use Railway or upgrade to Render's paid tier.

### 4. Run migration + seed

Use the Render **Shell** tab on the `synckar-api` service:

```bash
python -c "
import psycopg2, os
conn = psycopg2.connect(os.environ['DATABASE_URL'])
with open('migrations/init.sql') as f:
    conn.cursor().execute(f.read())
conn.commit()
"
python scripts/seed_data.py
```

---

## Quick local test before deploying

```bash
# From synckar/
docker compose up --build

# In another terminal — seed data
docker compose exec synckar-api python scripts/seed_data.py

# Run demo scenario A (SWS → departments)
docker compose exec synckar-api python scripts/demo_scenario_a.py

# Open dashboard
open http://localhost:18080/dashboard
```

---

## Architecture of the deployed system

```
Browser
  └── /dashboard  ──────────────────────────────────────────────────────┐
                                                                         │
  Railway / Render                                                        │
  ┌─────────────────────────────────────────────────────────────────┐   │
  │  synckar-api  (FastAPI + Kafka consumer thread)                  │◄──┘
  │    GET /health, /api/audit, /api/dlq, /api/webhooks             │
  │    GET /dashboard  →  serves React SPA                          │
  └──────────────┬──────────────────────────────────────────────────┘
                 │ Celery tasks
  ┌──────────────▼──────────────────────────────────────────────────┐
  │  synckar-worker  (Celery worker — propagation tasks)            │
  └──────────────┬──────────────────────────────────────────────────┘
                 │ Beat schedule
  ┌──────────────▼──────────────────────────────────────────────────┐
  │  synckar-beat  (Celery beat — polling + outbox drain)           │
  └─────────────────────────────────────────────────────────────────┘

  External services:
    PostgreSQL  ←  audit_ledger, outbox, conflict_log, DLQ
    Redis       ←  idempotency keys, circuit breakers, watermarks
    Kafka       ←  sws.changes, dept.*.changes topics

  Mock systems (separate services):
    synckar-mock-sws        :8000
    synckar-mock-shop       :8001
    synckar-mock-factories  :8002
```
