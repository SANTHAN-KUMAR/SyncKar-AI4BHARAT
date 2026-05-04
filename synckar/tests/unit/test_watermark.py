"""
Unit tests for Watermark persistence — Redis cache + PostgreSQL fallback.
Verifies that watermarks survive Redis restarts (persisted to DB).
"""

from unittest import mock

import pytest
import redis


def _make_mock_conn():
    conn = mock.Mock()
    cursor = mock.Mock()
    conn.cursor.return_value = cursor
    return conn, cursor


def test_get_watermark_returns_redis_cached_value():
    """get_watermark returns the Redis-cached value when available."""
    with (
        mock.patch("synckar.pipeline.watermark.redis.Redis") as mock_redis_cls,
        mock.patch("synckar.pipeline.watermark.db") as mock_db,
    ):
        r = mock.Mock()
        r.get.return_value = "2024-01-15T10:00:00Z"
        mock_redis_cls.from_url.return_value = r

        from synckar.pipeline.watermark import get_watermark
        result = get_watermark("sws", "2000-01-01T00:00:00Z")

    assert result == "2024-01-15T10:00:00Z"
    # DB should NOT be queried when Redis has the value
    mock_db.get_conn.assert_not_called()


def test_get_watermark_falls_back_to_db_when_redis_miss():
    """get_watermark falls back to PostgreSQL when Redis has no value."""
    conn, cursor = _make_mock_conn()
    cursor.fetchone.return_value = ("2024-01-10T08:00:00Z",)

    with (
        mock.patch("synckar.pipeline.watermark.redis.Redis") as mock_redis_cls,
        mock.patch("synckar.pipeline.watermark.db") as mock_db,
    ):
        r = mock.Mock()
        r.get.return_value = None  # Redis miss
        mock_redis_cls.from_url.return_value = r
        mock_db.get_conn.return_value = conn

        from synckar.pipeline.watermark import get_watermark
        result = get_watermark("sws", "2000-01-01T00:00:00Z")

    assert result == "2024-01-10T08:00:00Z"
    mock_db.get_conn.assert_called_once()


def test_get_watermark_returns_default_when_both_miss():
    """get_watermark returns the default when neither Redis nor DB has a value."""
    conn, cursor = _make_mock_conn()
    cursor.fetchone.return_value = None  # No DB row

    with (
        mock.patch("synckar.pipeline.watermark.redis.Redis") as mock_redis_cls,
        mock.patch("synckar.pipeline.watermark.db") as mock_db,
    ):
        r = mock.Mock()
        r.get.return_value = None
        mock_redis_cls.from_url.return_value = r
        mock_db.get_conn.return_value = conn

        from synckar.pipeline.watermark import get_watermark
        result = get_watermark("factories", "2000-01-01T00:00:00Z")

    assert result == "2000-01-01T00:00:00Z"


def test_set_watermark_writes_to_both_redis_and_db():
    """set_watermark must persist to both Redis and PostgreSQL."""
    conn, cursor = _make_mock_conn()

    with (
        mock.patch("synckar.pipeline.watermark.redis.Redis") as mock_redis_cls,
        mock.patch("synckar.pipeline.watermark.db") as mock_db,
    ):
        r = mock.Mock()
        mock_redis_cls.from_url.return_value = r
        mock_db.get_conn.return_value = conn

        from synckar.pipeline.watermark import set_watermark
        set_watermark("sws", "2024-02-01T12:00:00Z")

    # Redis must be updated
    r.set.assert_called_once_with("watermark:sws", "2024-02-01T12:00:00Z")
    # DB must be updated (UPSERT)
    cursor.execute.assert_called_once()
    upsert_sql = cursor.execute.call_args[0][0]
    assert "INSERT INTO poller_state" in upsert_sql
    assert "ON CONFLICT" in upsert_sql
    conn.commit.assert_called_once()


def test_set_watermark_still_writes_db_when_redis_down():
    """set_watermark must persist to DB even when Redis is unavailable."""
    conn, cursor = _make_mock_conn()

    with (
        mock.patch("synckar.pipeline.watermark.redis.Redis") as mock_redis_cls,
        mock.patch("synckar.pipeline.watermark.db") as mock_db,
    ):
        r = mock.Mock()
        r.set.side_effect = redis.ConnectionError("Redis down")
        mock_redis_cls.from_url.return_value = r
        mock_db.get_conn.return_value = conn

        from synckar.pipeline.watermark import set_watermark
        set_watermark("factories", "2024-02-01T12:00:00Z")

    # DB must still be updated despite Redis failure
    cursor.execute.assert_called_once()
    conn.commit.assert_called_once()
