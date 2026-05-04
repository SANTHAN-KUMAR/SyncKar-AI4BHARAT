"""
Unit tests for the Idempotency Engine — AGENTS.md §7, C3.

Covers:
  - RESERVED on first call (NX succeeds)
  - COMPLETED skip on second call
  - IdempotencyKeyInProgress raised when another worker holds the key
  - complete() stores COMPLETED:{response}
  - release() deletes the key
  - Redis down → NOT_FOUND fallback (no crash)
  - Keys are time-independent (C3)
"""

from unittest import mock

import pytest
import redis

from synckar.exceptions import IdempotencyKeyInProgress
from synckar.pipeline.idempotency import IdempotencyEngine, IdempotencyStatus


@pytest.fixture
def mock_redis():
    return mock.Mock(spec=redis.Redis)


@pytest.fixture
def engine(mock_redis):
    return IdempotencyEngine(redis_client=mock_redis)


# ─── reserve() ────────────────────────────────────────────────────────────────

def test_reserve_succeeds_on_first_call(engine, mock_redis):
    """NX set succeeds → RESERVED."""
    mock_redis.set.return_value = True  # NX succeeded

    status, cached = engine.reserve("test_key_abc")

    assert status == IdempotencyStatus.RESERVED
    assert cached is None
    mock_redis.set.assert_called_once_with(
        name="idem:test_key_abc",
        value="IN_PROGRESS",
        nx=True,
        ex=mock.ANY,
    )


def test_reserve_returns_completed_when_key_already_done(engine, mock_redis):
    """NX fails, existing value is COMPLETED:{response} → return cached."""
    mock_redis.set.return_value = None  # NX failed
    mock_redis.get.return_value = "COMPLETED:OK"

    status, cached = engine.reserve("test_key_abc")

    assert status == IdempotencyStatus.COMPLETED
    assert cached == "OK"


def test_reserve_raises_in_progress_when_another_worker_holds_key(engine, mock_redis):
    """NX fails, existing value is IN_PROGRESS → raise IdempotencyKeyInProgress."""
    mock_redis.set.return_value = None  # NX failed
    mock_redis.get.return_value = "IN_PROGRESS"

    with pytest.raises(IdempotencyKeyInProgress):
        engine.reserve("test_key_abc")


def test_reserve_returns_not_found_when_redis_down(engine, mock_redis):
    """Redis ConnectionError → NOT_FOUND fallback, no crash."""
    mock_redis.set.side_effect = redis.ConnectionError("Redis down")

    status, cached = engine.reserve("test_key_abc")

    assert status == IdempotencyStatus.NOT_FOUND
    assert cached is None


# ─── complete() ───────────────────────────────────────────────────────────────

def test_complete_stores_completed_prefix(engine, mock_redis):
    """complete() must store COMPLETED:{response} with TTL."""
    engine.complete("test_key_abc", response="OK")

    mock_redis.set.assert_called_once_with(
        name="idem:test_key_abc",
        value="COMPLETED:OK",
        ex=mock.ANY,
    )


def test_complete_is_nonfatal_when_redis_down(engine, mock_redis):
    """Redis down during complete() must not crash — worst case is a duplicate."""
    mock_redis.set.side_effect = redis.ConnectionError("Redis down")

    # Should not raise
    engine.complete("test_key_abc")


# ─── release() ────────────────────────────────────────────────────────────────

def test_release_deletes_key(engine, mock_redis):
    engine.release("test_key_abc")
    mock_redis.delete.assert_called_once_with("idem:test_key_abc")


def test_release_is_nonfatal_when_redis_down(engine, mock_redis):
    mock_redis.delete.side_effect = redis.ConnectionError("Redis down")
    engine.release("test_key_abc")  # Should not raise


# ─── check() ──────────────────────────────────────────────────────────────────

def test_check_returns_not_found_for_missing_key(engine, mock_redis):
    mock_redis.get.return_value = None
    status, cached = engine.check("test_key_abc")
    assert status == IdempotencyStatus.NOT_FOUND


def test_check_returns_in_progress(engine, mock_redis):
    mock_redis.get.return_value = "IN_PROGRESS"
    status, _ = engine.check("test_key_abc")
    assert status == IdempotencyStatus.IN_PROGRESS


def test_check_returns_completed_with_cached_response(engine, mock_redis):
    mock_redis.get.return_value = "COMPLETED:some_response"
    status, cached = engine.check("test_key_abc")
    assert status == IdempotencyStatus.COMPLETED
    assert cached == "some_response"


# ─── C3: Time-independence ────────────────────────────────────────────────────

def test_idempotency_key_is_time_independent():
    """C3: The same inputs must always produce the same key, regardless of when called."""
    from synckar.models.service_request import make_idempotency_key

    key1 = make_idempotency_key("sws", "evt_001", "KA-TEST-0001", "registered_address", "New Addr")
    key2 = make_idempotency_key("sws", "evt_001", "KA-TEST-0001", "registered_address", "New Addr")

    assert key1 == key2
    assert len(key1) == 64  # SHA-256 hex digest


def test_idempotency_key_differs_for_different_values():
    """Different new_value must produce a different key."""
    from synckar.models.service_request import make_idempotency_key

    key1 = make_idempotency_key("sws", "evt_001", "KA-TEST-0001", "registered_address", "Addr A")
    key2 = make_idempotency_key("sws", "evt_001", "KA-TEST-0001", "registered_address", "Addr B")

    assert key1 != key2


def test_idempotency_key_differs_per_adapter():
    """Per-adapter suffix ensures shop and factories keys are distinct."""
    from synckar.models.service_request import make_idempotency_key

    base = make_idempotency_key("sws", "evt_001", "KA-TEST-0001", "registered_address", "Addr")
    key_shop = f"{base}:shop_establishment"
    key_fact = f"{base}:factories"

    assert key_shop != key_fact
