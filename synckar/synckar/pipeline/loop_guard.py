"""Loop guard to prevent echo propagation."""

import hashlib

import redis
import structlog

from synckar.config import settings

logger = structlog.get_logger()


def _redis_client() -> redis.Redis:
    return redis.Redis.from_url(settings.redis.url, decode_responses=True)


def _key(system_id: str, ubid: str, field_name: str, new_value: str) -> str:
    raw = f"{system_id}|{ubid}|{field_name}|{new_value}"
    digest = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"loop_guard:{system_id}:{ubid}:{field_name}:{digest}"


def mark_write(system_id: str, ubid: str, field_name: str, new_value: str) -> None:
    """Record a recent outbound write to suppress echo on next poll."""
    try:
        r = _redis_client()
        r.set(
            _key(system_id, ubid, field_name, new_value),
            "1",
            ex=settings.pipeline.loop_guard_ttl_seconds,
        )
    except redis.ConnectionError:
        logger.debug("loop_guard_redis_unavailable")


def is_recent_write(system_id: str, ubid: str, field_name: str, new_value: str) -> bool:
    """Check if this change was recently written by SyncKar."""
    try:
        r = _redis_client()
        return r.exists(_key(system_id, ubid, field_name, new_value)) == 1
    except redis.ConnectionError:
        return False
