FROM python:3.11-slim AS python-base

WORKDIR /app

# ─── Install Python dependencies ───
COPY pyproject.toml .
COPY synckar/ synckar/
COPY schema_registry/ schema_registry/
COPY migrations/ migrations/
COPY scripts/ scripts/

RUN pip install --no-cache-dir .

# ─── Generate RSA keys for audit signing (BSA 2023) ───
# In production, override with RSA_PRIVATE_KEY_BASE64 env var instead.
RUN python scripts/generate_rsa_keys.py

# ─── Build the React dashboard ───
FROM node:20-alpine AS dashboard-builder

WORKDIR /dashboard
COPY dashboard/package.json dashboard/package-lock.json ./
RUN npm ci --prefer-offline

COPY dashboard/ ./
# VITE_API_URL is intentionally left unset here — the dashboard calls
# the same origin at runtime, so no build-time URL is needed.
RUN npm run build

# ─── Final image ───
FROM python-base AS final

# Copy the built dashboard into the expected location
COPY --from=dashboard-builder /dashboard/dist /app/dashboard/dist

# Default: run the FastAPI API server
CMD ["uvicorn", "synckar.api.main:app", "--host", "0.0.0.0", "--port", "8080"]
