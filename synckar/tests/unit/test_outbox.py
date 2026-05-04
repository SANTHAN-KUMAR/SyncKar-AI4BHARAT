"""
Unit tests for the Transactional Outbox — ARCHITECTURE.md §4.

Covers:
  - write_to_outbox inserts a PENDING row and returns an ID
  - drain_outbox marks only successfully delivered rows as PUBLISHED
  - drain_outbox leaves failed deliveries as PENDING (retry on next cycle)
  - drain_outbox returns 0 when Kafka producer init fails
  - _resolve_topic maps source systems to correct topics
"""

from unittest import mock
from uuid import uuid4

import pytest

from synckar.models.service_request import (
    CanonicalServiceRequest,
    RequestType,
    SourceSystem,
)


def _make_event(source_system: SourceSystem = SourceSystem.SWS) -> CanonicalServiceRequest:
    return CanonicalServiceRequest(
        ubid="KA-TEST-0001",
        request_type=RequestType.ADDRESS_CHANGE,
        source_system=source_system,
        source_event_id="evt_001",
        field_name="registered_address",
        new_value="New Address",
        raw_payload={},
    )


# ─── write_to_outbox ──────────────────────────────────────────────────────────

def test_write_to_outbox_inserts_pending_row():
    """write_to_outbox must INSERT a PENDING row and return the outbox ID."""
    event = _make_event()
    fake_id = uuid4()

    mock_conn = mock.Mock()
    mock_cursor = mock.Mock()
    mock_cursor.fetchone.return_value = (fake_id,)
    mock_conn.cursor.return_value = mock_cursor

    with (
        mock.patch("synckar.pipeline.outbox._get_db_connection", return_value=mock_conn),
        mock.patch("synckar.pipeline.outbox.db") as mock_db,
    ):
        mock_db.put_conn = mock.Mock()
        from synckar.pipeline.outbox import write_to_outbox
        result = write_to_outbox(event, topic="sws.changes")

    assert result == fake_id
    mock_cursor.execute.assert_called_once()
    # Verify the INSERT includes 'PENDING'
    call_args = mock_cursor.execute.call_args[0]
    assert "PENDING" in call_args[0]
    mock_conn.commit.assert_called_once()


def test_write_to_outbox_rolls_back_on_error():
    """write_to_outbox must rollback on DB error."""
    event = _make_event()

    mock_conn = mock.Mock()
    mock_cursor = mock.Mock()
    mock_cursor.execute.side_effect = Exception("DB error")
    mock_conn.cursor.return_value = mock_cursor

    with (
        mock.patch("synckar.pipeline.outbox._get_db_connection", return_value=mock_conn),
        mock.patch("synckar.pipeline.outbox.db") as mock_db,
    ):
        mock_db.put_conn = mock.Mock()
        from synckar.pipeline.outbox import write_to_outbox
        with pytest.raises(Exception, match="DB error"):
            write_to_outbox(event, topic="sws.changes")

    mock_conn.rollback.assert_called_once()


# ─── drain_outbox ─────────────────────────────────────────────────────────────

def test_drain_outbox_marks_only_delivered_rows_published():
    """
    Bug fix: drain_outbox must only mark rows PUBLISHED after Kafka delivery
    callbacks confirm success — not optimistically before flush().
    """
    from synckar.pipeline.outbox import drain_outbox

    event = _make_event()
    outbox_id = uuid4()
    payload_str = event.model_dump_json()

    mock_conn = mock.Mock()
    mock_cursor = mock.Mock()
    mock_cursor.fetchall.return_value = [
        (outbox_id, payload_str, "KA-TEST-0001", "sws", None),
    ]
    mock_conn.cursor.return_value = mock_cursor

    # Simulate a producer that calls the callback with success
    def fake_produce(topic, key, value, callback):
        # Simulate successful delivery
        msg_mock = mock.Mock()
        msg_mock.topic.return_value = topic
        msg_mock.partition.return_value = 0
        msg_mock.offset.return_value = 1
        callback(None, msg_mock)  # err=None → success

    mock_producer = mock.Mock()
    mock_producer.produce.side_effect = fake_produce
    mock_producer.flush.return_value = None

    with (
        mock.patch("synckar.pipeline.outbox._get_db_connection", return_value=mock_conn),
        mock.patch("synckar.pipeline.outbox.db") as mock_db,
        mock.patch("synckar.pipeline.outbox._get_kafka_producer", return_value=mock_producer),
    ):
        mock_db.put_conn = mock.Mock()
        count = drain_outbox()

    assert count == 1
    # UPDATE must reference the delivered outbox_id
    update_call = mock_cursor.execute.call_args_list[-1]
    assert "PUBLISHED" in update_call[0][0]
    assert outbox_id in update_call[0][1]
    mock_conn.commit.assert_called()


def test_drain_outbox_does_not_mark_failed_deliveries_published():
    """
    Rows whose Kafka delivery callback fires with an error must remain PENDING.
    """
    from synckar.pipeline.outbox import drain_outbox

    event = _make_event()
    outbox_id = uuid4()
    payload_str = event.model_dump_json()

    mock_conn = mock.Mock()
    mock_cursor = mock.Mock()
    mock_cursor.fetchall.return_value = [
        (outbox_id, payload_str, "KA-TEST-0001", "sws", None),
    ]
    mock_conn.cursor.return_value = mock_cursor

    # Simulate a producer that calls the callback with an error
    def fake_produce_fail(topic, key, value, callback):
        err_mock = mock.Mock()
        err_mock.__str__ = lambda self: "Kafka error"
        callback(err_mock, None)  # err != None → failure

    mock_producer = mock.Mock()
    mock_producer.produce.side_effect = fake_produce_fail
    mock_producer.flush.return_value = None

    with (
        mock.patch("synckar.pipeline.outbox._get_db_connection", return_value=mock_conn),
        mock.patch("synckar.pipeline.outbox.db") as mock_db,
        mock.patch("synckar.pipeline.outbox._get_kafka_producer", return_value=mock_producer),
    ):
        mock_db.put_conn = mock.Mock()
        count = drain_outbox()

    # No rows delivered → count = 0, no UPDATE executed
    assert count == 0
    # Ensure no PUBLISHED update was issued
    for call in mock_cursor.execute.call_args_list:
        assert "PUBLISHED" not in call[0][0]


def test_drain_outbox_returns_zero_when_kafka_unavailable():
    """If Kafka producer init fails, drain_outbox returns 0 without crashing."""
    from synckar.pipeline.outbox import drain_outbox

    mock_conn = mock.Mock()

    with (
        mock.patch("synckar.pipeline.outbox._get_db_connection", return_value=mock_conn),
        mock.patch("synckar.pipeline.outbox.db") as mock_db,
        mock.patch(
            "synckar.pipeline.outbox._get_kafka_producer",
            side_effect=Exception("Kafka unavailable"),
        ),
    ):
        mock_db.get_conn.return_value = mock_conn
        count = drain_outbox()

    assert count == 0


# ─── _resolve_topic ───────────────────────────────────────────────────────────

def test_resolve_topic_maps_correctly():
    """Each source system maps to its correct Kafka topic."""
    from synckar.pipeline.outbox import _resolve_topic

    assert _resolve_topic("sws") == "sws.changes"
    assert _resolve_topic("shop_establishment") == "dept.shop_establishment.changes"
    assert _resolve_topic("factories") == "dept.factories.changes"


def test_resolve_topic_unknown_falls_back_to_sws():
    """Unknown source system falls back to sws.changes topic."""
    from synckar.pipeline.outbox import _resolve_topic

    assert _resolve_topic("unknown_system") == "sws.changes"
