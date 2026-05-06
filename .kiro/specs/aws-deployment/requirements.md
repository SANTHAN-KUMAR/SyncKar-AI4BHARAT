# Requirements Document

## Introduction

Deploy the SyncKar prototype stack to an existing AWS EC2 t3.small instance so that the full application — including the React dashboard, FastAPI API, Celery workers, Celery Beat scheduler, mock department systems, PostgreSQL, Redis, and Redpanda (Kafka) — is accessible via the instance's public IP address. The deployment must be fast to execute, use Docker Compose (mirroring the local stack), and require no additional AWS managed services. This is a prototype/demo deployment, not a production environment.

**All five services run on the same single EC2 instance in a single Docker Compose stack.** There are no separate instances, no separate deployments, and no external managed services. The entire system starts with one command: `docker compose up --build -d`.

The EC2 instance already has Docker, Docker Compose, and Redpanda installed. Redpanda will run as a container alongside the other services, reusing the existing local `docker-compose.yml` with environment-specific overrides.

The source code is hosted at: `https://github.com/SANTHAN-KUMAR/SyncKar-AI4BHARAT.git`

## Glossary

- **EC2_Instance**: The existing AWS EC2 t3.small instance that hosts ALL SyncKar services — infrastructure, mock systems, and application — in a single Docker Compose stack.
- **Deployment_Script**: A shell script that automates cloning, configuring, and starting the stack on the EC2_Instance.
- **Compose_Stack**: The set of five Docker Compose services (redpanda, postgres, redis, mock-systems, synckar-api) defined in `synckar/docker-compose.yml`, all running on the same EC2_Instance.
- **SyncKar_API**: The FastAPI application container that also embeds the Celery worker, Celery Beat scheduler, and serves the React dashboard as static files.
- **Mock_Systems**: The combined Flask container serving mock SWS, Shop Establishment, and Factories department endpoints at `/sws`, `/shop`, and `/factories` path prefixes. This container runs on the same EC2_Instance as all other services — it is NOT deployed separately.
- **Dashboard**: The React (Vite) single-page application served as static files from the SyncKar_API container at the `/dashboard` path.
- **Public_URL**: The EC2 instance's raw public IP address and port used to access the Dashboard and API from a browser.
- **RSA_Keys**: The RSA private/public key pair used for BSA 2023 audit log signing, injected via the `RSA_PRIVATE_KEY_BASE64` environment variable.
- **Env_File**: The `.env` file on the EC2_Instance containing all runtime configuration for the Compose_Stack.
- **Security_Group**: The AWS EC2 security group controlling inbound/outbound traffic to the EC2_Instance.
- **GitHub_Repo**: The SyncKar source repository at `https://github.com/SANTHAN-KUMAR/SyncKar-AI4BHARAT.git`.

---

## Requirements

### Requirement 1: EC2 Security Group Configuration

**User Story:** As a demo presenter, I want the SyncKar dashboard and API to be reachable from any browser, so that I can demonstrate the prototype to stakeholders without network access issues.

#### Acceptance Criteria

1. THE Security_Group SHALL allow inbound TCP traffic on port 18080 from any source IP (0.0.0.0/0).
2. THE Security_Group SHALL allow inbound TCP traffic on port 22 (SSH) to permit remote administration.
3. WHEN a browser sends an HTTP request to `http://<EC2_public_IP>:18080/dashboard`, THE SyncKar_API SHALL return the Dashboard HTML response.

---

### Requirement 2: Repository Deployment to EC2

**User Story:** As a developer, I want the SyncKar source code to be present on the EC2 instance, so that Docker Compose can build and run all containers.

#### Acceptance Criteria

1. THE Deployment_Script SHALL clone the GitHub_Repo (`https://github.com/SANTHAN-KUMAR/SyncKar-AI4BHARAT.git`) into a designated directory on the EC2_Instance (e.g. `~/SyncKar-AI4BHARAT`).
2. WHEN the repository already exists at the target directory, THE Deployment_Script SHALL perform a `git pull` to update it rather than re-cloning.
3. THE Deployment_Script SHALL change the working directory to the `synckar/` subdirectory of the cloned repository before executing any Docker Compose commands.

---

### Requirement 3: Single-Instance Co-location of All Services

**User Story:** As a developer, I want all five services — including mock systems — to run on the same EC2 instance in the same Docker Compose stack, so that the deployment is simple to manage and requires no cross-instance networking.

#### Acceptance Criteria

1. THE Compose_Stack SHALL include all five services — `redpanda`, `postgres`, `redis`, `mock-systems`, and `synckar-api` — running on the same EC2_Instance.
2. THE Mock_Systems container SHALL run as part of the same Compose_Stack on the same EC2_Instance as the SyncKar_API, postgres, redis, and redpanda containers.
3. THE Deployment_Script SHALL NOT provision, reference, or connect to any external instance or managed service for any component of the Compose_Stack.
4. WHEN the Deployment_Script completes, THE operator SHALL be able to verify all five containers are running by executing `docker compose ps` from the `synckar/` directory on the EC2_Instance.
5. THE entire Compose_Stack SHALL start with a single command (`docker compose up --build -d`) from the `synckar/` directory on the EC2_Instance.

---

### Requirement 4: Environment Configuration

**User Story:** As a developer, I want all runtime configuration to be supplied via environment variables, so that no secrets or host-specific values are hardcoded in the repository.

#### Acceptance Criteria

1. THE Deployment_Script SHALL generate or copy an Env_File at `synckar/.env` on the EC2_Instance before starting the Compose_Stack.
2. THE Env_File SHALL contain values for `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`, `KAFKA_BOOTSTRAP_SERVERS`, `MOCK_SWS_BASE_URL`, `MOCK_SHOP_BASE_URL`, and `MOCK_FACTORIES_BASE_URL`.
3. THE Env_File SHALL set `KAFKA_BOOTSTRAP_SERVERS` to `redpanda:9092` and `KAFKA_SECURITY_PROTOCOL` to `PLAINTEXT` so that the containerised Redpanda is used.
4. THE Env_File SHALL set `MOCK_SWS_BASE_URL`, `MOCK_SHOP_BASE_URL`, and `MOCK_FACTORIES_BASE_URL` to `http://mock-systems:8000/sws`, `http://mock-systems:8000/shop`, and `http://mock-systems:8000/factories` respectively, using Docker Compose internal DNS to reach the co-located Mock_Systems container.
5. THE Env_File SHALL contain `RSA_PRIVATE_KEY_BASE64` set to the base64-encoded RSA private key so that the SyncKar_API can sign audit records without mounting key files.
6. IF `RSA_PRIVATE_KEY_BASE64` is absent from the Env_File, THEN THE SyncKar_API SHALL fall back to generating a new RSA key pair at container startup via `scripts/generate_rsa_keys.py`.

---

### Requirement 5: Docker Compose Stack Startup

**User Story:** As a developer, I want all five services to start reliably in the correct order, so that the SyncKar_API does not fail due to missing dependencies.

#### Acceptance Criteria

1. THE Deployment_Script SHALL start the Compose_Stack using `docker compose up --build -d` from the `synckar/` directory.
2. WHEN the Compose_Stack starts, THE SyncKar_API container SHALL wait for the `postgres`, `redis`, and `redpanda` containers to pass their health checks before starting, as defined by the `depends_on` conditions in `docker-compose.yml`.
3. THE Compose_Stack SHALL expose port 18080 on the EC2_Instance, mapped to port 8080 inside the SyncKar_API container.
4. WHEN all containers are running, THE SyncKar_API SHALL respond with HTTP 200 to a GET request at `http://localhost:18080/health`.

---

### Requirement 6: Database Initialisation

**User Story:** As a developer, I want the PostgreSQL schema to be created on first deployment, so that the SyncKar_API can persist audit records and outbox events immediately.

#### Acceptance Criteria

1. THE Deployment_Script SHALL run the database migration after the `postgres` container is healthy by executing `python scripts/run_migrations.py` inside the SyncKar_API container.
2. WHEN the migration has already been applied, THE migration script SHALL complete without error (idempotent execution).
3. THE Deployment_Script SHALL run `python scripts/seed_data.py` inside the SyncKar_API container to populate demo data after the migration succeeds.

---

### Requirement 7: Dashboard Accessibility

**User Story:** As a demo presenter, I want to open the SyncKar dashboard in a browser using only the EC2 public IP, so that I can run the demo without configuring DNS or a load balancer.

#### Acceptance Criteria

1. WHEN a browser sends a GET request to `http://<EC2_public_IP>:18080/dashboard`, THE SyncKar_API SHALL serve the compiled React SPA (built into the Docker image at `/app/dashboard/dist`).
2. THE SyncKar_API SHALL serve all Dashboard static assets (JS, CSS, icons) from the same origin so that no cross-origin requests are required.
3. WHEN the Dashboard makes API calls (e.g. `/api/stats`, `/api/audit`), THE SyncKar_API SHALL respond with valid JSON within 5 seconds under normal load.

---

### Requirement 8: Mock Systems Availability

**User Story:** As a demo presenter, I want the mock department systems to be reachable by the SyncKar_API on the same machine, so that polling and propagation scenarios work end-to-end during the demo without any cross-instance networking.

#### Acceptance Criteria

1. THE Mock_Systems container SHALL run on the same EC2_Instance as the SyncKar_API container, communicating over the Docker Compose internal network (`synckar` bridge network).
2. THE Mock_Systems container SHALL expose HTTP endpoints at `/sws`, `/shop`, and `/factories` path prefixes on port 8000 within the Docker Compose network.
3. WHEN the SyncKar_API polls a mock department endpoint, THE Mock_Systems container SHALL respond with HTTP 200 and a valid JSON payload within 2 seconds.
4. IF the Mock_Systems container is unavailable, THEN THE SyncKar_API SHALL activate the circuit breaker for the affected adapter and continue operating for other adapters.

---

### Requirement 9: Deployment Verification

**User Story:** As a developer, I want a quick smoke test I can run after deployment, so that I can confirm the stack is working before the demo.

#### Acceptance Criteria

1. THE Deployment_Script SHALL print the Public_URL (`http://<EC2_public_IP>:18080/dashboard`) to stdout upon successful completion.
2. WHEN the Deployment_Script completes, THE operator SHALL be able to verify the deployment by running `curl http://localhost:18080/health` on the EC2_Instance and receiving HTTP 200.
3. THE Deployment_Script SHALL exit with a non-zero status code if any critical step fails (image build failure, container startup failure, or migration failure), so that the operator is alerted immediately.

---

### Requirement 10: Restart and Persistence

**User Story:** As a developer, I want the stack to survive an EC2 instance reboot, so that the demo environment does not need to be manually restarted after routine maintenance.

#### Acceptance Criteria

1. THE Compose_Stack SHALL be configured with `restart: unless-stopped` on all containers so that Docker automatically restarts them after an EC2_Instance reboot.
2. WHEN the EC2_Instance restarts, THE Compose_Stack SHALL resume within 2 minutes without manual intervention.
3. THE PostgreSQL and Redis containers SHALL use named Docker volumes (`pg_data`, `redis_data`) so that data persists across container restarts.
