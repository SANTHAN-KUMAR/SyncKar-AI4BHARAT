"""Watermark persistence with Redis cache and PostgreSQL fallback."""

import redis
import structlog

from synckar import db
from synckar.config import settings

logger = structlog.get_logger()


def _redis_key(system_id: str) -> str:
    return f"watermark:{system_id}"


def get_watermark(system_id: str, default: str) -> str:
    r = redis.Redis.from_url(settings.redis.url, decode_responses=True)
    try:
        cached = r.get(_redis_key(system_id))
        if cached:
            return cached
    except redis.ConnectionError:
        logger.debug("watermark_redis_unavailable", system_id=system_id)

    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT watermark FROM poller_state WHERE system_id = %s",
            (system_id,),
        )
        row = cursor.fetchone()
        if row and row[0]:
            value = row[0]
            try:
                r.set(_redis_key(system_id), value)
            except redis.ConnectionError:
                pass
            return value
        return default
    finally:
        db.put_conn(conn)


def set_watermark(system_id: str, value: str) -> None:
    r = redis.Redis.from_url(settings.redis.url, decode_responses=True)
    try:
        r.set(_redis_key(system_id), value)
    except redis.ConnectionError:
        logger.debug("watermark_redis_unavailable", system_id=system_id)

    conn = db.get_conn()
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO poller_state (system_id, watermark, updated_at)
            VALUES (%s, %s, now())
            ON CONFLICT (system_id) DO UPDATE
            SET watermark = EXCLUDED.watermark, updated_at = now()
            """,
            (system_id, value),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        db.put_conn(conn)
