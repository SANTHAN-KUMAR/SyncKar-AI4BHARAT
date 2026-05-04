FROM python:3.11-slim

WORKDIR /app

# Install only what the mock systems need
RUN pip install --no-cache-dir fastapi uvicorn[standard] pydantic

# Copy the entire mock_systems directory so relative imports work
COPY mock_systems/ mock_systems/

# Make the package importable
RUN touch mock_systems/__init__.py \
    && touch mock_systems/mock_sws/__init__.py \
    && touch mock_systems/mock_dept_shop/__init__.py \
    && touch mock_systems/mock_dept_factories/__init__.py

EXPOSE 8000

CMD ["sh", "-c", "uvicorn mock_systems.combined_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
