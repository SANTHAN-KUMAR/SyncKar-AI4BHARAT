"""Health and stats routes."""

import redis
import structlog
import psycopg2.extras
from fastapi import APIRouter

from synckar.config import settings
from synckar import db

logger = structlog.get_logger()
router = APIRouter()


@router.get("/health")
def health_check():
    """Check connectivity to Kafka, Redis, PostgreSQL."""
    checks = {}

    # Redis
    try:
        r = redis.Redis.from_url(settings.redis.url)
        r.ping()
        checks["redis"] = "healthy"
    except Exception as e:
        checks["redis"] = f"unhealthy: {e}"

    # PostgreSQL
    try:
        conn = db.get_conn()
        db.put_conn(conn)
        checks["postgres"] = "healthy"
    except Exception as e:
        checks["postgres"] = f"unhealthy: {e}"

    # Kafka
    try:
        from confluent_kafka.admin import AdminClient
        admin = AdminClient({"bootstrap.servers": settings.kafka.bootstrap_servers})
        admin.list_topics(timeout=3)
        checks["kafka"] = "healthy"
    except Exception as e:
        checks["kafka"] = f"unhealthy: {e}"

    all_healthy = all(v == "healthy" for v in checks.values())
    return {
        "status": "healthy" if all_healthy else "degraded",
        "checks": checks,
        "system": "synckar",
    }


@router.get("/api/stats")
def get_stats():
    """Dashboard stats — event counts, conflict counts, DLQ depth."""
    try:
        conn = db.get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM audit_ledger")
        audit_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM audit_ledger WHERE conflict_detected = true")
        conflict_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM conflict_log")
        conflict_log_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM dead_letter_queue WHERE status = 'PENDING'")
        dlq_depth = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM outbox WHERE status = 'PENDING'")
        outbox_pending = cursor.fetchone()[0]

        db.put_conn(conn)

        return {
            "audit_entries": audit_count,
            "conflicts_detected": conflict_count,
            "conflict_records": conflict_log_count,
            "dlq_depth": dlq_depth,
            "outbox_pending": outbox_pending,
        }
    except Exception as e:
        logger.error("stats_error", error=str(e))
        return {"error": str(e)}
