"""
Unit tests for Loop Guard — prevents echo propagation.
Verifies that outbound writes are marked and pollers skip them on next cycle.
"""

from unittest import mock

import pytest
import redis

from synckar.pipeline.loop_guard import mark_write, is_recent_write


@pytest.fixture
def mock_redis_client():
    with mock.patch("synckar.pipeline.loop_guard._redis_client") as mock_fn:
        r = mock.Mock(spec=redis.Redis)
        mock_fn.return_value = r
        yield r


def test_mark_write_sets_redis_key(mock_redis_client):
    """mark_write must set a Redis key with TTL."""
    mark_write("factories", "KA-TEST-0001", "registered_address", "New Address")
    mock_redis_client.set.assert_called_once()
    call_kwargs = mock_redis_client.set.call_args
    # Key must contain system, ubid, field
    key_arg = call_kwargs[0][0]
    assert "factories" in key_arg
    assert "KA-TEST-0001" in key_arg
    assert "registered_address" in key_arg
    # TTL must be set
    assert call_kwargs[1].get("ex") is not None or call_kwargs[0][2] is not None


def test_is_recent_write_returns_true_when_key_exists(mock_redis_client):
    """is_recent_write returns True when the key exists in Redis."""
    mock_redis_client.exists.return_value = 1
    result = is_recent_write("factories", "KA-TEST-0001", "registered_address", "New Address")
    assert result is True


def test_is_recent_write_returns_false_when_key_absent(mock_redis_client):
    """is_recent_write returns False when the key is not in Redis."""
    mock_redis_client.exists.return_value = 0
    result = is_recent_write("factories", "KA-TEST-0001", "registered_address", "New Address")
    assert result is False


def test_is_recent_write_returns_false_on_redis_down(mock_redis_client):
    """Redis down → returns False (conservative: allow propagation)."""
    mock_redis_client.exists.side_effect = redis.ConnectionError("Redis down")
    result = is_recent_write("factories", "KA-TEST-0001", "registered_address", "New Address")
    assert result is False


def test_mark_write_is_nonfatal_on_redis_down(mock_redis_client):
    """Redis down during mark_write must not crash."""
    mock_redis_client.set.side_effect = redis.ConnectionError("Redis down")
    # Should not raise
    mark_write("factories", "KA-TEST-0001", "registered_address", "New Address")


def test_different_values_produce_different_keys(mock_redis_client):
    """Two different values for the same field must produce different Redis keys."""
    mark_write("factories", "KA-TEST-0001", "registered_address", "Address A")
    key_a = mock_redis_client.set.call_args[0][0]

    mock_redis_client.reset_mock()
    mark_write("factories", "KA-TEST-0001", "registered_address", "Address B")
    key_b = mock_redis_client.set.call_args[0][0]

    assert key_a != key_b


def test_same_inputs_produce_same_key(mock_redis_client):
    """Same inputs must always produce the same key (deterministic)."""
    mark_write("sws", "KA-TEST-0002", "authorized_signatory", "Rajesh Kumar")
    key_1 = mock_redis_client.set.call_args[0][0]

    mock_redis_client.reset_mock()
    mark_write("sws", "KA-TEST-0002", "authorized_signatory", "Rajesh Kumar")
    key_2 = mock_redis_client.set.call_args[0][0]

    assert key_1 == key_2
