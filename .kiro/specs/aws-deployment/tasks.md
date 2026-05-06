# Implementation Plan: AWS EC2 Deployment

## Overview

Create the four deployment artifacts needed to run the full SyncKar stack on a single EC2 t3.small instance: a Docker Compose override file, an env template, a one-shot setup script, and an updated README section.

## Tasks

- [x] 1. Create `synckar/docker-compose.override.yml`
  - Write the EC2-specific Compose override that adds `restart: unless-stopped` to all five services (`redpanda`, `postgres`, `redis`, `mock-systems`, `synckar-api`)
  - Override the Redpanda `command` block to set `--memory 512M` so the broker fits within the t3.small's 2 GB RAM while keeping `--advertise-kafka-addr PLAINTEXT://redpanda:9092` unchanged
  - Add a header comment explaining usage: `docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d`
  - _Requirements: 5.1, 10.1, 10.3_

- [x] 2. Create `synckar/.env.ec2`
  - Write the env template with all required keys pre-filled for the Docker Compose internal network: `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `KAFKA_BOOTSTRAP_SERVERS=redpanda:9092`, `KAFKA_SECURITY_PROTOCOL=PLAINTEXT`
  - Set mock system URLs to Docker Compose internal DNS: `MOCK_SWS_BASE_URL=http://mock-systems:8000/sws`, `MOCK_SHOP_BASE_URL=http://mock-systems:8000/shop`, `MOCK_FACTORIES_BASE_URL=http://mock-systems:8000/factories`
  - Include `RSA_PRIVATE_KEY_BASE64=` as an empty placeholder with a comment explaining how to generate it (`base64 -w 0 keys/private.pem`)
  - Include all pipeline config vars (`CONFLICT_WINDOW_SECONDS`, `IDEMPOTENCY_TTL_SECONDS`, circuit breaker settings, polling intervals)
  - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 3. Create `synckar/setup.sh`
  - Write a `bash` script with `set -euo pipefail` at the top
  - Add prerequisite checks for `git`, `docker`, and `docker compose` plugin; exit 1 with a clear error message if any are missing
  - Clone `https://github.com/SANTHAN-KUMAR/SyncKar-AI4BHARAT.git` into `~/SyncKar-AI4BHARAT`; if the directory already exists perform `git pull` instead
  - Copy `.env.ec2` to `.env` if `.env` does not already exist; warn (but do not exit) if `RSA_PRIVATE_KEY_BASE64` is empty in the resulting `.env`
  - Run `docker compose -f docker-compose.yml -f docker-compose.override.yml up --build -d` from the `synckar/` directory
  - Poll `http://localhost:18080/health` in a retry loop (30 attempts × 5 s) and exit 1 with a log message if the API never becomes healthy
  - Run `docker compose exec -T synckar-api python scripts/run_migrations.py` then `python scripts/seed_data.py`
  - Fetch the public IP from the EC2 instance metadata service (`http://169.254.169.254/latest/meta-data/public-ipv4`) and print the dashboard URL, health URL, and API docs URL on success
  - _Requirements: 2.1, 2.2, 2.3, 3.5, 4.1, 5.1, 6.1, 6.2, 6.3, 9.1, 9.3_

- [x] 4. Update `synckar/README.md` — add AWS deployment section
  - Add an "AWS EC2 Deployment" section after the existing local-dev instructions
  - Document the one-time prerequisites: PEM key, EC2 public IP, security group rules (port 22 and 18080 open)
  - Show the three-step deployment flow: SSH in → upload/create `setup.sh` and `.env.ec2` → run `bash setup.sh`
  - Include the optional RSA key injection step (`base64 -w 0 keys/private.pem` → append to `.env`)
  - List the post-deployment smoke-test commands (`docker compose ps`, `curl http://localhost:18080/health`, browser URL)
  - Add a redeployment snippet (`git pull` + `docker compose up --build -d`)
  - _Requirements: 9.1, 9.2_

- [x] 5. Checkpoint — verify artifacts are consistent
  - Ensure all five services in `docker-compose.override.yml` match the service names in `docker-compose.yml`
  - Ensure every env key referenced in `setup.sh` and `docker-compose.override.yml` is present in `.env.ec2`
  - Ensure `setup.sh` is executable (`chmod +x`) and passes a `bash -n` syntax check
  - Ensure all tests pass, ask the user if questions arise.
