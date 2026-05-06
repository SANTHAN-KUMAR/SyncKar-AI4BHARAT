# Design Document: AWS EC2 Deployment

## Overview

This document describes how to deploy the SyncKar prototype stack to a single AWS EC2 t3.small instance. All five services — `redpanda`, `postgres`, `redis`, `mock-systems`, and `synckar-api` — run in one Docker Compose stack on the same machine. There are no external managed services, no separate instances, and no load balancers. The goal is a single-command deployment that a developer can execute in under 10 minutes.

The deployment strategy is:

1. User SSHes into the EC2 instance once using their PEM key.
2. User runs `setup.sh` on the instance (clones repo, writes `.env`, starts stack, runs migrations, seeds data).
3. User opens `http://<EC2_public_IP>:18080/dashboard` in a browser.

This is intentionally simpler than a remote-execution approach (no need to pass secrets over SSH flags, no dependency on local `ssh` client quirks).

### Key Design Decisions

**Redpanda advertise address**: The `--advertise-kafka-addr` flag in `docker-compose.yml` is already set to `PLAINTEXT://redpanda:9092`. All consumers (the `synckar-api` container) connect using the Docker Compose service name `redpanda:9092` over the internal `synckar` bridge network. This works correctly within the Docker network and requires no change for EC2 deployment. The EC2 private IP is not needed here.

**No remote-execution script**: A script that SSHes in and runs commands remotely requires passing secrets (RSA key base64) as shell arguments or heredocs, which is error-prone and leaks values into shell history. The simpler approach — SSH in once, run `setup.sh` on the instance — keeps secrets local to the instance.

**RSA keys**: The `RSA_PRIVATE_KEY_BASE64` env var is the preferred injection method. The Dockerfile already runs `generate_rsa_keys.py` as a fallback, so if the operator omits this var, the container generates a fresh key pair at build time. For a demo this is acceptable.

**Port exposure**: Only port 18080 (the API/dashboard) needs to be publicly accessible. Ports 9092 (Redpanda), 15432 (Postgres), and 6379 (Redis) are bound to `0.0.0.0` in the base `docker-compose.yml` for local dev convenience. The EC2 security group should only open 18080 and 22 to the internet; the other ports are accessible only within the instance.

---

## Architecture

All five containers run on one EC2 t3.small instance inside a single Docker bridge network (`synckar`). The host exposes only port 18080 to the internet.

```mermaid
graph TB
    subgraph EC2["EC2 t3.small (single instance)"]
        subgraph Docker["Docker bridge network: synckar"]
            RP["redpanda\n:9092 (internal)\n:9644 (admin)"]
            PG["postgres:16-alpine\n:5432 (internal)"]
            RD["redis:7-alpine\n:6379 (internal)"]
            MS["mock-systems\n:8000 (internal)\n/sws /shop /factories"]
            API["synckar-api\nFastAPI + Celery + Beat\nReact dashboard\n:8080 (internal)"]
        end
        HOST[":18080 (host)"]
    end

    BROWSER["Browser / curl"] -->|"HTTP :18080"| HOST
    HOST -->|"port map 18080→8080"| API
    API -->|"redpanda:9092"| RP
    API -->|"postgres:5432"| PG
    API -->|"redis:6379"| RD
    API -->|"mock-systems:8000"| MS
```

**Container responsibilities:**

| Container | Image | Role |
|---|---|---|
| `redpanda` | `redpanda/redpanda:latest` | Kafka-compatible message broker |
| `postgres` | `postgres:16-alpine` | Persistent relational store (audit, outbox, mappings) |
| `redis` | `redis:7-alpine` | Celery broker/backend, idempotency cache, circuit breaker state |
| `mock-systems` | Built from `mock_systems/Dockerfile` | Combined Flask app serving mock SWS, Shop, Factories endpoints |
| `synckar-api` | Built from `Dockerfile` | FastAPI app + embedded Celery worker + Celery Beat + React dashboard static files |

---

## Components and Interfaces

### docker-compose.override.yml

The override file adds EC2-specific settings on top of the base `docker-compose.yml` without modifying it. It adds `restart: unless-stopped` to all services so containers survive an instance reboot, and reduces Redpanda's memory allocation to fit within the t3.small's 2 GB RAM.

The base `docker-compose.yml` already uses `redpanda:9092` as the advertise address, which is correct for intra-container communication. No change is needed there.

### setup.sh

A shell script the operator runs once on the EC2 instance. It handles:

1. Checking prerequisites (git, docker, docker compose)
2. Cloning or pulling the repository
3. Writing `.env` from the template (prompts for `RSA_PRIVATE_KEY_BASE64` if not already set)
4. Starting the stack with `docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d`
5. Waiting for the `synckar-api` health endpoint to respond
6. Running database migrations
7. Seeding demo data
8. Printing the dashboard URL

### .env.ec2

A template `.env` file with all EC2-specific values pre-filled. The operator copies this to `synckar/.env` and fills in `RSA_PRIVATE_KEY_BASE64`. All service URLs use Docker Compose internal DNS names (not `localhost`).

### Security Group

The EC2 security group must have two inbound rules:

| Port | Protocol | Source | Purpose |
|---|---|---|---|
| 22 | TCP | Your IP (or 0.0.0.0/0) | SSH access |
| 18080 | TCP | 0.0.0.0/0 | Dashboard and API access |

All other ports (9092, 15432, 6379, 8000) should remain closed to the internet. They are accessible within the instance via Docker's bridge network.

---

## Data Models

No new data models are introduced by this deployment. The existing schema is initialised by `migrations/init.sql` via `scripts/run_migrations.py`. Named Docker volumes persist data across restarts:

| Volume | Container | Contents |
|---|---|---|
| `pg_data` | postgres | PostgreSQL data directory |
| `redis_data` | redis | Redis RDB/AOF snapshots |
| `redpanda_data` | redpanda | Redpanda topic data |

---

## Artifact Designs

### docker-compose.override.yml

```yaml
# docker-compose.override.yml
# EC2-specific overrides. Applied on top of docker-compose.yml.
# Usage: docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d

version: "3.9"

services:
  redpanda:
    restart: unless-stopped
    # Reduce memory for t3.small (2 GB total RAM).
    # Override the --memory flag from the base compose file.
    command:
      - redpanda
      - start
      - --overprovisioned
      - --smp
      - "1"
      - --memory
      - 512M
      - --reserve-memory
      - 0M
      - --node-id
      - "0"
      - --check=false
      - --kafka-addr
      - PLAINTEXT://0.0.0.0:9092
      - --advertise-kafka-addr
      - PLAINTEXT://redpanda:9092
      - --rpc-addr
      - 0.0.0.0:33145
      - --advertise-rpc-addr
      - redpanda:33145

  postgres:
    restart: unless-stopped

  redis:
    restart: unless-stopped

  mock-systems:
    restart: unless-stopped

  synckar-api:
    restart: unless-stopped
```

**Why 512M for Redpanda?** The t3.small has 2 GB RAM. With all five containers running, Redpanda's default 1 GB allocation leaves too little headroom. 512 MB is sufficient for a single-broker demo with low message volume.

**Why keep `--advertise-kafka-addr PLAINTEXT://redpanda:9092`?** All Kafka clients (`synckar-api`) connect from within the same Docker bridge network. Docker's internal DNS resolves `redpanda` to the container's IP. Using the EC2 private IP here would only be needed if clients connected from outside the Docker network, which they don't.

---

### .env.ec2 Template

```dotenv
# .env.ec2 — Copy to synckar/.env on the EC2 instance.
# Fill in RSA_PRIVATE_KEY_BASE64 before running setup.sh.

# ─── Database ───
DATABASE_URL=postgresql://synckar_app:synckar_app@postgres:5432/synckar
DB_POOL_MIN=2
DB_POOL_MAX=10

# ─── Redis ───
REDIS_URL=redis://redis:6379/0

# ─── Celery ───
CELERY_BROKER_URL=redis://redis:6379/1
CELERY_RESULT_BACKEND=redis://redis:6379/2

# ─── Kafka / Redpanda ───
KAFKA_BOOTSTRAP_SERVERS=redpanda:9092
KAFKA_SECURITY_PROTOCOL=PLAINTEXT

# ─── Mock System URLs (Docker Compose internal DNS) ───
MOCK_SWS_BASE_URL=http://mock-systems:8000/sws
MOCK_SHOP_BASE_URL=http://mock-systems:8000/shop
MOCK_FACTORIES_BASE_URL=http://mock-systems:8000/factories

# ─── RSA Signing (BSA 2023 audit compliance) ───
# Generate with: base64 -w 0 keys/private.pem
# If omitted, the container generates a fresh key pair at build time (demo only).
RSA_PRIVATE_KEY_BASE64=

# ─── Pipeline Config ───
CONFLICT_WINDOW_SECONDS=900
IDEMPOTENCY_TTL_SECONDS=259200
CIRCUIT_BREAKER_FAILURE_THRESHOLD=5
CIRCUIT_BREAKER_WINDOW_SECONDS=120
CIRCUIT_BREAKER_PROBE_INTERVAL_SECONDS=60
CONSUMER_TASK_TIMEOUT_SECONDS=30
LOOP_GUARD_TTL_SECONDS=900
WEBHOOK_RATE_LIMIT_PER_MINUTE=60

# ─── Polling Intervals ───
SWS_POLL_INTERVAL_SECONDS=5
SHOP_POLL_INTERVAL_SECONDS=10
FACTORIES_POLL_INTERVAL_SECONDS=10
```

---

### setup.sh Script

```bash
#!/usr/bin/env bash
# setup.sh — Run this ONCE on the EC2 instance to deploy SyncKar.
# Usage: bash setup.sh
# Prerequisites on EC2: git, docker, docker compose plugin

set -euo pipefail

REPO_URL="https://github.com/SANTHAN-KUMAR/SyncKar-AI4BHARAT.git"
REPO_DIR="$HOME/SyncKar-AI4BHARAT"
SYNCKAR_DIR="$REPO_DIR/synckar"
HEALTH_URL="http://localhost:18080/health"
HEALTH_RETRIES=30
HEALTH_INTERVAL=5

# ─── Colours ───
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC} $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# ─── 1. Prerequisites ───
info "Checking prerequisites..."
for cmd in git docker; do
  if ! command -v "$cmd" &>/dev/null; then
    error "$cmd is not installed. Please install it and re-run."
    exit 1
  fi
done
if ! docker compose version &>/dev/null; then
  error "docker compose plugin not found. Please install it and re-run."
  exit 1
fi
info "Prerequisites OK."

# ─── 2. Clone or pull repo ───
if [ -d "$REPO_DIR/.git" ]; then
  info "Repository already exists — pulling latest changes..."
  git -C "$REPO_DIR" pull
else
  info "Cloning repository..."
  git clone "$REPO_URL" "$REPO_DIR"
fi

# ─── 3. Write .env ───
ENV_FILE="$SYNCKAR_DIR/.env"
ENV_TEMPLATE="$SYNCKAR_DIR/.env.ec2"

if [ ! -f "$ENV_FILE" ]; then
  if [ -f "$ENV_TEMPLATE" ]; then
    info "Copying .env.ec2 to .env..."
    cp "$ENV_TEMPLATE" "$ENV_FILE"
  else
    error ".env.ec2 template not found at $ENV_TEMPLATE"
    error "Please create it from the design document and re-run."
    exit 1
  fi
else
  info ".env already exists — skipping copy."
fi

# Prompt for RSA key if not set
if ! grep -q "^RSA_PRIVATE_KEY_BASE64=.\+" "$ENV_FILE" 2>/dev/null; then
  warn "RSA_PRIVATE_KEY_BASE64 is not set in .env."
  warn "The container will generate a fresh key pair at build time (demo mode)."
  warn "To use your own key: base64 -w 0 keys/private.pem >> .env"
fi

# ─── 4. Start the stack ───
info "Building and starting Docker Compose stack..."
cd "$SYNCKAR_DIR"
docker compose \
  -f docker-compose.yml \
  -f docker-compose.override.yml \
  up --build -d

# ─── 5. Wait for API health ───
info "Waiting for synckar-api to become healthy (up to $((HEALTH_RETRIES * HEALTH_INTERVAL))s)..."
for i in $(seq 1 $HEALTH_RETRIES); do
  if curl -sf "$HEALTH_URL" >/dev/null 2>&1; then
    info "synckar-api is healthy."
    break
  fi
  if [ "$i" -eq "$HEALTH_RETRIES" ]; then
    error "synckar-api did not become healthy in time."
    error "Check logs: docker compose logs synckar-api"
    exit 1
  fi
  echo -n "."
  sleep "$HEALTH_INTERVAL"
done
echo ""

# ─── 6. Run migrations ───
info "Running database migrations..."
docker compose exec -T synckar-api python scripts/run_migrations.py

# ─── 7. Seed demo data ───
info "Seeding demo data..."
docker compose exec -T synckar-api python scripts/seed_data.py

# ─── 8. Print summary ───
EC2_IP=$(curl -sf http://169.254.169.254/latest/meta-data/public-ipv4 2>/dev/null || echo "<EC2_PUBLIC_IP>")
DASHBOARD_URL="http://${EC2_IP}:18080/dashboard"

echo ""
echo -e "${GREEN}╔══════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║           SyncKar deployment complete!                  ║${NC}"
echo -e "${GREEN}╠══════════════════════════════════════════════════════════╣${NC}"
echo -e "${GREEN}║  Dashboard:  ${DASHBOARD_URL}${NC}"
echo -e "${GREEN}║  Health:     http://${EC2_IP}:18080/health${NC}"
echo -e "${GREEN}║  API docs:   http://${EC2_IP}:18080/docs${NC}"
echo -e "${GREEN}╚══════════════════════════════════════════════════════════╝${NC}"
echo ""
info "Container status:"
docker compose ps
```

---

## Step-by-Step Deployment Instructions

### Prerequisites (one-time, done before deployment)

**On your local machine:**

1. Confirm you have the PEM key file (e.g. `hackathon_key.pem`).
2. Get the EC2 instance's public IP from the AWS console.
3. Confirm the EC2 security group has inbound rules for port 22 and port 18080.

**To open port 18080 via AWS CLI (if not already open):**
```bash
# Replace sg-xxxxxxxx with your security group ID
aws ec2 authorize-security-group-ingress \
  --group-id sg-xxxxxxxx \
  --protocol tcp \
  --port 18080 \
  --cidr 0.0.0.0/0
```

**To get your RSA private key as base64 (optional but recommended):**
```bash
# Run from the repo root on your local machine
base64 -w 0 synckar/keys/private.pem
# Copy the output — you'll paste it into .env on the EC2 instance
```

---

### Step 1 — SSH into the EC2 instance

```bash
chmod 400 hackathon_key.pem
ssh -i hackathon_key.pem ubuntu@<EC2_PUBLIC_IP>
```

---

### Step 2 — Upload setup.sh and .env.ec2 to the instance

From your local machine (in a separate terminal):

```bash
# Upload the setup script
scp -i hackathon_key.pem synckar/setup.sh ubuntu@<EC2_PUBLIC_IP>:~/setup.sh

# Upload the env template
scp -i hackathon_key.pem synckar/.env.ec2 ubuntu@<EC2_PUBLIC_IP>:~/SyncKar-AI4BHARAT/synckar/.env.ec2
```

Alternatively, you can create these files directly on the instance using `nano` or `cat` after SSHing in.

---

### Step 3 — Run setup.sh on the instance

Back in your SSH session:

```bash
chmod +x ~/setup.sh
bash ~/setup.sh
```

The script will:
- Clone the repo (or pull if it already exists)
- Copy `.env.ec2` to `synckar/.env`
- Warn if `RSA_PRIVATE_KEY_BASE64` is not set
- Run `docker compose up --build -d` with the override file
- Wait for the health endpoint to respond
- Run migrations
- Seed demo data
- Print the dashboard URL

**Expected duration:** 3–8 minutes (mostly Docker image build time).

---

### Step 4 — Set RSA_PRIVATE_KEY_BASE64 (optional)

If you want to use your existing RSA key for audit signing:

```bash
# On the EC2 instance, after setup.sh has run
echo "RSA_PRIVATE_KEY_BASE64=$(base64 -w 0 ~/SyncKar-AI4BHARAT/synckar/keys/private.pem)" \
  >> ~/SyncKar-AI4BHARAT/synckar/.env

# Restart the API container to pick up the new env var
cd ~/SyncKar-AI4BHARAT/synckar
docker compose -f docker-compose.yml -f docker-compose.override.yml restart synckar-api
```

If you skip this step, the container uses the key generated during `docker build` — fine for a demo.

---

### Step 5 — Verify the deployment

```bash
# On the EC2 instance
cd ~/SyncKar-AI4BHARAT/synckar

# Check all 5 containers are running
docker compose ps

# Check the health endpoint
curl http://localhost:18080/health

# Check the dashboard responds
curl -I http://localhost:18080/dashboard
```

Open in a browser: `http://<EC2_PUBLIC_IP>:18080/dashboard`

---

### Redeployment (after code changes)

```bash
cd ~/SyncKar-AI4BHARAT/synckar

# Pull latest code
git -C ~/SyncKar-AI4BHARAT pull

# Rebuild and restart
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d

# Re-run migrations (idempotent — safe to run again)
docker compose exec synckar-api python scripts/run_migrations.py
```

---

## Verification Steps

### Smoke tests (run on the EC2 instance)

```bash
# 1. All 5 containers running
docker compose ps
# Expected: redpanda, postgres, redis, mock-systems, synckar-api all "Up"

# 2. API health
curl http://localhost:18080/health
# Expected: HTTP 200, {"status": "ok"} or similar

# 3. Dashboard HTML
curl -s http://localhost:18080/dashboard | head -5
# Expected: <!DOCTYPE html> ...

# 4. API docs
curl -s http://localhost:18080/docs | head -5
# Expected: HTML for Swagger UI

# 5. Mock systems reachable from within the network
docker compose exec synckar-api curl -s http://mock-systems:8000/sws/health
docker compose exec synckar-api curl -s http://mock-systems:8000/shop/health
docker compose exec synckar-api curl -s http://mock-systems:8000/factories/health
# Expected: HTTP 200 for each

# 6. Kafka broker healthy
docker compose exec redpanda rpk cluster info --brokers localhost:9092
# Expected: cluster info output with 1 broker

# 7. Seeded data present
curl -s http://localhost:18080/api/stats
# Expected: JSON with business counts > 0
```

### From your local machine (external access test)

```bash
# Replace with your actual EC2 public IP
EC2_IP=<EC2_PUBLIC_IP>

curl http://${EC2_IP}:18080/health
curl -I http://${EC2_IP}:18080/dashboard
curl http://${EC2_IP}:18080/api/stats
```

---

## Running Demo Scenarios

All three demo scenarios are Python scripts in `synckar/scripts/`. Run them from inside the `synckar-api` container so they can reach the mock services via Docker DNS.

### Setup: set SYNCKAR_URL for the scripts

```bash
EC2_IP=<EC2_PUBLIC_IP>
```

### Scenario A — SWS → Department Propagation

Updates a business address in mock SWS and watches SyncKar propagate it to Shop Establishment and Factories.

```bash
# On the EC2 instance
cd ~/SyncKar-AI4BHARAT/synckar
docker compose exec synckar-api python scripts/demo_scenario_a.py
```

Or from your local machine (the script uses `SYNCKAR_URL` and the mock URLs):

```bash
cd synckar
SYNCKAR_URL=http://<EC2_PUBLIC_IP>:18080 \
MOCK_SWS_BASE_URL=http://<EC2_PUBLIC_IP>:8000/sws \
MOCK_SHOP_BASE_URL=http://<EC2_PUBLIC_IP>:8000/shop \
MOCK_FACTORIES_BASE_URL=http://<EC2_PUBLIC_IP>:8000/factories \
python scripts/demo_scenario_a.py
```

> Note: Running from local requires port 8000 to be open in the security group. Running from inside the container (first option) is simpler and doesn't require opening extra ports.

### Scenario B and C

```bash
docker compose exec synckar-api python scripts/demo_scenario_b.py
docker compose exec synckar-api python scripts/demo_scenario_c.py
```

### Reset state between demos

```bash
docker compose exec synckar-api python scripts/reset_state.py
docker compose exec synckar-api python scripts/seed_data.py
```

### Watch live logs during a demo

```bash
# All services
docker compose logs -f

# Just the API (Celery tasks, propagation events)
docker compose logs -f synckar-api

# Just Redpanda
docker compose logs -f redpanda
```

---

## Error Handling

### Build failures

If `docker compose up --build` fails:

```bash
# Check which service failed
docker compose logs <service-name>

# Common causes:
# - npm ci fails: check Node version in dashboard/package.json
# - pip install fails: check pyproject.toml dependencies
# - Out of disk space: docker system prune -f
```

### Migration failures

```bash
# Check postgres is healthy first
docker compose ps postgres

# Re-run migration manually
docker compose exec synckar-api python scripts/run_migrations.py

# If schema is corrupted, reset (DESTROYS ALL DATA):
docker compose down -v
docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d
docker compose exec synckar-api python scripts/run_migrations.py
docker compose exec synckar-api python scripts/seed_data.py
```

### Container won't start

```bash
# Check logs
docker compose logs <container-name>

# Check resource usage (t3.small has 2 GB RAM)
free -h
docker stats --no-stream
```

### Redpanda out of memory

If Redpanda crashes with OOM errors, the 512M allocation in `docker-compose.override.yml` may need adjustment. Check available memory with `free -h` and reduce other services if needed.

### Port 18080 not reachable from browser

1. Confirm the EC2 security group has an inbound rule for TCP 18080 from 0.0.0.0/0.
2. Confirm the container is running: `docker compose ps synckar-api`.
3. Confirm the port mapping: `docker compose port synckar-api 8080` should return `0.0.0.0:18080`.

---

## Testing Strategy

This feature is a deployment configuration — it involves shell scripts, Docker Compose YAML, and environment files. Property-based testing is not applicable here (see prework analysis: all acceptance criteria are SMOKE, INTEGRATION, or EXAMPLE tests).

**Smoke tests** (verify configuration is correct before deploying):
- Parse `.env.ec2` and assert all required keys are present
- Validate `docker-compose.override.yml` is valid YAML and contains `restart: unless-stopped` for all services
- Verify `setup.sh` contains `set -euo pipefail` (fail-fast on errors)

**Integration tests** (run after deployment):
- `curl http://localhost:18080/health` returns HTTP 200
- `docker compose ps` shows 5 containers in `Up` state
- `curl http://localhost:18080/dashboard` returns HTML
- Mock system health endpoints respond within 2 seconds
- `curl http://localhost:18080/api/stats` returns JSON with non-zero business counts

**Example tests** (specific scenarios):
- Running `setup.sh` twice: second run does `git pull` instead of `git clone`
- Running `run_migrations.py` twice: second run exits 0 (idempotent)
- Starting `synckar-api` without `RSA_PRIVATE_KEY_BASE64`: container starts and generates keys

All integration tests are run manually by the operator following the verification steps above. No automated CI pipeline is required for this prototype deployment.
