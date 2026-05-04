"""
SyncKar Configuration — pydantic-settings, env-driven.
No hardcoded URLs, credentials, or system IDs (AGENTS.md §13).
All configuration is loaded from environment variables or .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class KafkaSettings(BaseSettings):
    """Kafka connection and topic configuration."""
    bootstrap_servers: str = Field(
        default="localhost:9092",
        alias="KAFKA_BOOTSTRAP_SERVERS",
    )
    security_protocol: str = Field(
        default="PLAINTEXT",
        alias="KAFKA_SECURITY_PROTOCOL",
    )
    sasl_mechanism: Optional[str] = Field(
        default=None,
        alias="KAFKA_SASL_MECHANISM",
    )
    sasl_username: Optional[str] = Field(
        default=None,
        alias="KAFKA_SASL_USERNAME",
    )
    sasl_password: Optional[str] = Field(
        default=None,
        alias="KAFKA_SASL_PASSWORD",
    )
    ssl_ca_path: Optional[str] = Field(
        default=None,
        alias="KAFKA_SSL_CA_PATH",
    )

    # Topic names — matching ARCHITECTURE.md §13
    topic_sws_changes: str = "sws.changes"
    topic_dept_shop_changes: str = "dept.shop_establishment.changes"
    topic_dept_factories_changes: str = "dept.factories.changes"
    topic_propagation_dlq: str = "propagation.dlq"
    topic_audit_events: str = "audit.events"

    model_config = {"env_prefix": "", "extra": "ignore"}


class DatabaseSettings(BaseSettings):
    """PostgreSQL connection configuration."""
    url: str = Field(
        default="postgresql://synckar_app:synckar_app@localhost:5432/synckar",
        alias="DATABASE_URL",
    )
    pool_min: int = Field(default=2, alias="DB_POOL_MIN")
    pool_max: int = Field(default=10, alias="DB_POOL_MAX")

    model_config = {"env_prefix": "", "extra": "ignore"}


class RedisSettings(BaseSettings):
    """Redis connection configuration."""
    url: str = Field(
        default="redis://localhost:6379/0",
        alias="REDIS_URL",
    )

    model_config = {"env_prefix": "", "extra": "ignore"}


class PipelineSettings(BaseSettings):
    """Pipeline configuration — conflict window, idempotency, circuit breaker."""
    # Conflict detection — ARCHITECTURE.md §6, AGENTS.md §8
    conflict_window_seconds: int = Field(
        default=900,  # 15 minutes
        alias="CONFLICT_WINDOW_SECONDS",
    )

    # Idempotency — AGENTS.md §7
    idempotency_ttl_seconds: int = Field(
        default=259200,  # 72 hours
        alias="IDEMPOTENCY_TTL_SECONDS",
    )
    idempotency_in_progress_ttl_seconds: int = Field(
        default=3600,  # 1 hour
        alias="IDEMPOTENCY_IN_PROGRESS_TTL_SECONDS",
    )

    # Circuit breaker — AGENTS.md §9
    circuit_breaker_failure_threshold: int = Field(
        default=5,
        alias="CIRCUIT_BREAKER_FAILURE_THRESHOLD",
    )
    circuit_breaker_window_seconds: int = Field(
        default=120,  # 2 minutes
        alias="CIRCUIT_BREAKER_WINDOW_SECONDS",
    )
    circuit_breaker_probe_interval_seconds: int = Field(
        default=60,
        alias="CIRCUIT_BREAKER_PROBE_INTERVAL_SECONDS",
    )

    # Retry — AGENTS.md §10
    max_retry_attempts: int = Field(default=10)
    retry_backoff_base_seconds: float = Field(default=1.0)
    retry_backoff_max_seconds: float = Field(default=60.0)

    # Consumer task timeout (Kafka -> Celery)
    consumer_task_timeout_seconds: int = Field(
        default=30,
        alias="CONSUMER_TASK_TIMEOUT_SECONDS",
    )

    # Loop-guard TTL to suppress echo propagation
    loop_guard_ttl_seconds: int = Field(
        default=900,
        alias="LOOP_GUARD_TTL_SECONDS",
    )

    model_config = {"env_prefix": "", "extra": "ignore"}


class MockSystemSettings(BaseSettings):
    """Mock system base URLs (for local dev and deployed environments)."""
    sws_base_url: str = Field(
        default="http://localhost:8000",
        alias="MOCK_SWS_BASE_URL",
    )
    shop_base_url: str = Field(
        default="http://localhost:8001",
        alias="MOCK_SHOP_BASE_URL",
    )
    factories_base_url: str = Field(
        default="http://localhost:8002",
        alias="MOCK_FACTORIES_BASE_URL",
    )

    model_config = {"env_prefix": "", "extra": "ignore"}


class PollingSettings(BaseSettings):
    """Per-adapter polling intervals."""
    sws_poll_interval_seconds: int = Field(
        default=5,
        alias="SWS_POLL_INTERVAL_SECONDS",
    )
    shop_poll_interval_seconds: int = Field(
        default=10,
        alias="SHOP_POLL_INTERVAL_SECONDS",
    )
    factories_poll_interval_seconds: int = Field(
        default=10,
        alias="FACTORIES_POLL_INTERVAL_SECONDS",
    )

    model_config = {"env_prefix": "", "extra": "ignore"}


class SigningSettings(BaseSettings):
    """RSA signing configuration for BSA 2023 audit compliance."""
    rsa_private_key_path: Optional[str] = Field(
        default="./keys/private.pem",
        alias="RSA_PRIVATE_KEY_PATH",
    )
    rsa_public_key_path: Optional[str] = Field(
        default="./keys/public.pem",
        alias="RSA_PUBLIC_KEY_PATH",
    )
    # Alternative: base64-encoded key in env var (for cloud deployment)
    rsa_private_key_base64: Optional[str] = Field(
        default=None,
        alias="RSA_PRIVATE_KEY_BASE64",
    )

    model_config = {"env_prefix": "", "extra": "ignore"}


class CelerySettings(BaseSettings):
    """Celery broker and result backend configuration."""
    broker_url: str = Field(
        default="redis://localhost:6379/1",
        alias="CELERY_BROKER_URL",
    )
    result_backend: str = Field(
        default="redis://localhost:6379/2",
        alias="CELERY_RESULT_BACKEND",
    )

    model_config = {"env_prefix": "", "extra": "ignore"}


class Settings(BaseSettings):
    """Root settings aggregator. All sub-settings are composed here."""
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    pipeline: PipelineSettings = Field(default_factory=PipelineSettings)
    mock_systems: MockSystemSettings = Field(default_factory=MockSystemSettings)
    polling: PollingSettings = Field(default_factory=PollingSettings)
    signing: SigningSettings = Field(default_factory=SigningSettings)
    celery: CelerySettings = Field(default_factory=CelerySettings)

    # Feature flags
    enable_ai_copilot: bool = Field(default=False, alias="ENABLE_AI_COPILOT")

    # Webhook settings
    webhook_rate_limit_per_minute: int = Field(
        default=60,
        alias="WEBHOOK_RATE_LIMIT_PER_MINUTE",
    )

    model_config = {"env_file": ".env", "env_prefix": "", "extra": "ignore"}


# Singleton instance — import this everywhere
settings = Settings()
