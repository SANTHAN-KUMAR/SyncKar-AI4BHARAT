"""
Unit tests for the Dispatcher — AGENTS.md §9, §10.

Covers:
  - IdempotencyKeyInProgress is re-raised (not swallowed) so Celery can retry
  - TargetWriteError is re-raised for Celery retry
  - PermanentWriteError propagates for DLQ routing
  - One adapter failing does NOT block the other (C9)
  - Successful propagation produces an audit row (C5)
  - UBID not found is silently skipped (C10)
"""

from unittest import mock
from uuid import uuid4

import pytest

from synckar.exceptions import (
    IdempotencyKeyInProgress,
    PermanentWriteError,
    TargetWriteError,
    UBIDNotFound,
)
from synckar.models.service_request import (
    CanonicalServiceRequest,
    RequestType,
    SourceSystem,
)
from synckar.pipeline.idempotency import IdempotencyStatus


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _make_event(
    source_system: SourceSystem = SourceSystem.SWS,
    field_name: str = "registered_address",
    new_value: str = "New Address",
) -> CanonicalServiceRequest:
    return CanonicalServiceRequest(
        ubid="KA-TEST-0001",
        request_type=RequestType.ADDRESS_CHANGE,
        source_system=source_system,
        source_event_id="evt_test_001",
        field_name=field_name,
        old_value="Old Address",
        new_value=new_value,
        raw_payload={},
        broker_sequence=42,
    )


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def patch_dispatcher_deps():
    """
    Patch all external dependencies of the dispatcher so tests run without
    Redis, Kafka, or real HTTP calls.
    """
    with (
        mock.patch("synckar.pipeline.dispatcher._get_redis") as mock_get_redis,
        mock.patch("synckar.pipeline.dispatcher._get_idempotency") as mock_get_idem,
        mock.patch("synckar.pipeline.dispatcher._get_conflict_detector") as mock_get_conflict,
        mock.patch("synckar.pipeline.dispatcher._get_circuit_breaker") as mock_get_cb,
        mock.patch("synckar.pipeline.dispatcher.write_audit_row") as mock_audit,
        mock.patch("synckar.pipeline.dispatcher.write_conflict_record") as mock_conflict_record,
    ):
        # Redis rate-limiter: always allow
        redis_mock = mock.Mock()
        redis_mock.pipeline.return_value.__enter__ = mock.Mock(return_value=redis_mock)
        redis_mock.pipeline.return_value.__exit__ = mock.Mock(return_value=False)
        pipe_mock = mock.Mock()
        pipe_mock.execute.return_value = [0, 1, 1, True]  # zcard = 1 → under limit
        redis_mock.pipeline.return_value = pipe_mock
        mock_get_redis.return_value = redis_mock

        # Idempotency: RESERVED by default (proceed)
        idem_mock = mock.Mock()
        idem_mock.reserve.return_value = (IdempotencyStatus.RESERVED, None)
        mock_get_idem.return_value = idem_mock

        # Conflict detector: no conflict by default
        conflict_mock = mock.Mock()
        conflict_mock.check_and_register.return_value = None
        mock_get_conflict.return_value = conflict_mock

        # Circuit breaker: CLOSED by default
        cb_mock = mock.Mock()
        cb_mock.is_call_permitted.return_value = True
        mock_get_cb.return_value = cb_mock

        yield {
            "redis": redis_mock,
            "idem": idem_mock,
            "conflict": conflict_mock,
            "cb": cb_mock,
            "audit": mock_audit,
            "conflict_record": mock_conflict_record,
        }


# ─── Tests: IdempotencyKeyInProgress propagation ──────────────────────────────

def test_idempotency_in_progress_is_reraised_not_swallowed(patch_dispatcher_deps):
    """
    Bug fix: IdempotencyKeyInProgress must propagate out of dispatch_sws_to_departments
    so the Celery task can retry with backoff.  Previously it was caught by the outer
    `except Exception` and silently dropped.
    """
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments

    patch_dispatcher_deps["idem"].reserve.side_effect = IdempotencyKeyInProgress(
        "Key in progress", system_id="shop_establishment", ubid="KA-TEST-0001"
    )

    event = _make_event()

    with pytest.raises(IdempotencyKeyInProgress):
        dispatch_sws_to_departments(event)


def test_idempotency_in_progress_factories_is_reraised(patch_dispatcher_deps):
    """Same fix applies to the Factories adapter path."""
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments

    call_count = {"n": 0}

    def idem_side_effect(key):
        call_count["n"] += 1
        # First call (shop_establishment) succeeds, second (factories) raises
        if call_count["n"] == 1:
            return (IdempotencyStatus.RESERVED, None)
        raise IdempotencyKeyInProgress(
            "Key in progress", system_id="factories", ubid="KA-TEST-0001"
        )

    patch_dispatcher_deps["idem"].reserve.side_effect = idem_side_effect

    # Patch shop client to succeed
    with (
        mock.patch("synckar.pipeline.dispatcher._get_shop_client") as mock_shop,
        mock.patch("synckar.pipeline.dispatcher._get_factories_client"),
    ):
        shop_client = mock.Mock()
        shop_client.update_record.return_value = {"updated_fields": ["Buss_Addr_Line1"]}
        mock_shop.return_value = shop_client

        event = _make_event()

        with pytest.raises(IdempotencyKeyInProgress):
            dispatch_sws_to_departments(event)


# ─── Tests: TargetWriteError propagation ──────────────────────────────────────

def test_target_write_error_is_reraised_for_celery_retry(patch_dispatcher_deps):
    """TargetWriteError must propagate so Celery retries with exponential backoff."""
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments

    with mock.patch("synckar.pipeline.dispatcher._get_shop_client") as mock_shop:
        shop_client = mock.Mock()
        shop_client.update_record.side_effect = TargetWriteError(
            "Shop Est 503", system_id="shop_establishment", ubid="KA-TEST-0001"
        )
        mock_shop.return_value = shop_client

        event = _make_event()

        with pytest.raises(TargetWriteError):
            dispatch_sws_to_departments(event)


# ─── Tests: C9 — one adapter failure does not block the other ─────────────────

def test_c9_shop_failure_does_not_block_factories(patch_dispatcher_deps):
    """
    C9: If Shop Establishment raises a non-retryable exception (e.g. TranslationError),
    Factories must still be attempted and succeed.
    """
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments
    from synckar.exceptions import TranslationError

    call_count = {"n": 0}

    def idem_side_effect(key):
        call_count["n"] += 1
        return (IdempotencyStatus.RESERVED, None)

    patch_dispatcher_deps["idem"].reserve.side_effect = idem_side_effect

    with (
        mock.patch("synckar.pipeline.dispatcher._get_shop_client") as mock_shop,
        mock.patch("synckar.pipeline.dispatcher._get_factories_client") as mock_fact,
        mock.patch("synckar.pipeline.dispatcher.shop_translate_outbound") as mock_shop_tx,
        mock.patch("synckar.pipeline.dispatcher.factories_translate_outbound") as mock_fact_tx,
    ):
        # Shop translation fails
        mock_shop_tx.side_effect = TranslationError(
            "Schema mismatch", system_id="shop_establishment"
        )

        # Factories succeeds
        mock_fact_tx.return_value = {"factory_address": "New Address"}
        fact_client = mock.Mock()
        fact_client.update_record.return_value = {"updated_fields": ["factory_address"]}
        mock_fact.return_value = fact_client

        event = _make_event()
        results = dispatch_sws_to_departments(event)

    # Shop failed, Factories succeeded
    assert "error" in results["shop_establishment"]
    assert results["factories"]["status"] == "success"


# ─── Tests: Idempotency COMPLETED skip ────────────────────────────────────────

def test_already_completed_event_is_skipped(patch_dispatcher_deps):
    """If idempotency key is COMPLETED, skip the API call and return cached result."""
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments

    patch_dispatcher_deps["idem"].reserve.return_value = (
        IdempotencyStatus.COMPLETED, "OK"
    )

    with mock.patch("synckar.pipeline.dispatcher._get_shop_client") as mock_shop:
        shop_client = mock.Mock()
        mock_shop.return_value = shop_client

        event = _make_event()
        results = dispatch_sws_to_departments(event)

    # API should NOT have been called
    shop_client.update_record.assert_not_called()
    assert results["shop_establishment"]["reason"] == "already_completed"


# ─── Tests: UBID not found skip (C10) ─────────────────────────────────────────

def test_ubid_not_found_is_silently_skipped(patch_dispatcher_deps):
    """C10: UBID not found in target system → skip, no retry, no DLQ."""
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments

    with (
        mock.patch("synckar.pipeline.dispatcher._get_shop_client") as mock_shop,
        mock.patch("synckar.pipeline.dispatcher._get_factories_client") as mock_fact,
        mock.patch("synckar.pipeline.dispatcher.shop_translate_outbound") as mock_tx,
        mock.patch("synckar.pipeline.dispatcher.factories_translate_outbound") as mock_fact_tx,
    ):
        mock_tx.return_value = {"Buss_Addr_Line1": "New Address"}
        shop_client = mock.Mock()
        shop_client.update_record.side_effect = UBIDNotFound(
            "UBID not found", system_id="shop_establishment", ubid="KA-TEST-0001"
        )
        mock_shop.return_value = shop_client
        
        mock_fact_tx.return_value = {"factory_address": "New Address"}
        fact_client = mock.Mock()
        fact_client.update_record.return_value = {"updated_fields": ["factory_address"]}
        mock_fact.return_value = fact_client

        event = _make_event()
        results = dispatch_sws_to_departments(event)

    assert results["shop_establishment"]["reason"] == "ubid_not_found"
    # Idempotency key must be released on skip
    patch_dispatcher_deps["idem"].release.assert_called()


# ─── Tests: Audit row written on success (C5) ─────────────────────────────────

def test_audit_row_written_on_successful_propagation(patch_dispatcher_deps):
    """C5: Every successful write must produce an audit row."""
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments

    with (
        mock.patch("synckar.pipeline.dispatcher._get_shop_client") as mock_shop,
        mock.patch("synckar.pipeline.dispatcher._get_factories_client") as mock_fact,
        mock.patch("synckar.pipeline.dispatcher.shop_translate_outbound") as mock_shop_tx,
        mock.patch("synckar.pipeline.dispatcher.factories_translate_outbound") as mock_fact_tx,
    ):
        mock_shop_tx.return_value = {"Buss_Addr_Line1": "New Address"}
        shop_client = mock.Mock()
        shop_client.update_record.return_value = {"updated_fields": ["Buss_Addr_Line1"]}
        mock_shop.return_value = shop_client

        mock_fact_tx.return_value = {"factory_address": "New Address"}
        fact_client = mock.Mock()
        fact_client.update_record.return_value = {"updated_fields": ["factory_address"]}
        mock_fact.return_value = fact_client

        event = _make_event()
        results = dispatch_sws_to_departments(event)

    # Two audit rows — one per adapter
    assert patch_dispatcher_deps["audit"].call_count == 2
    assert results["shop_establishment"]["status"] == "success"
    assert results["factories"]["status"] == "success"


# ─── Tests: Department → SWS propagation ──────────────────────────────────────

def test_dispatch_department_to_sws_success(patch_dispatcher_deps):
    """Factories → SWS propagation succeeds and writes audit row."""
    from synckar.pipeline.dispatcher import dispatch_department_to_sws

    with (
        mock.patch("synckar.pipeline.dispatcher._get_sws_client") as mock_sws,
        mock.patch("synckar.pipeline.dispatcher.sws_translate_outbound") as mock_tx,
    ):
        mock_tx.return_value = {"authorized_signatory": "Rajesh Kumar Sharma"}
        sws_client = mock.Mock()
        sws_client.update_business.return_value = {"updated_fields": ["authorized_signatory"]}
        mock_sws.return_value = sws_client

        event = _make_event(
            source_system=SourceSystem.FACTORIES,
            field_name="authorized_signatory",
            new_value="Rajesh Kumar Sharma",
        )
        results = dispatch_department_to_sws(event)

    assert results["sws"]["status"] == "success"
    patch_dispatcher_deps["audit"].assert_called_once()


def test_dispatch_department_to_sws_idem_in_progress_reraised(patch_dispatcher_deps):
    """IdempotencyKeyInProgress from dept→SWS path must also be re-raised."""
    from synckar.pipeline.dispatcher import dispatch_department_to_sws

    patch_dispatcher_deps["idem"].reserve.side_effect = IdempotencyKeyInProgress(
        "Key in progress", system_id="sws", ubid="KA-TEST-0002"
    )

    event = _make_event(source_system=SourceSystem.FACTORIES)

    with pytest.raises(IdempotencyKeyInProgress):
        dispatch_department_to_sws(event)


# ─── Tests: Conflict resolution branches ──────────────────────────────────────

def test_conflict_loser_is_skipped_and_audit_written(patch_dispatcher_deps):
    """
    When a conflict is detected and this event is the loser, it must be skipped
    and an audit row written (C5 — every write produces an audit row).
    """
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments
    from synckar.pipeline.conflict import ConflictWindowEntry, ResolutionPolicy
    from synckar.models.audit import ConflictAuditRecord
    from uuid import uuid4

    # Simulate an existing SWS entry in the conflict window
    existing = ConflictWindowEntry(
        source_system="sws",
        broker_sequence=100,
        correlation_id=str(uuid4()),
        value="SWS Winning Value",
    )
    patch_dispatcher_deps["conflict"].check_and_register.return_value = existing

    # Mock resolve_conflict to say the incoming event (dept) is the loser
    conflict_record = ConflictAuditRecord(
        correlation_id=uuid4(),
        ubid="KA-TEST-0001",
        field="registered_address",
        source_a_system="sws",
        source_a_value="SWS Winning Value",
        source_b_system="shop_establishment",
        source_b_value="Dept Losing Value",
        policy_applied=ResolutionPolicy.SWS_WINS.value,
        winning_value="SWS Winning Value",
        losing_value="Dept Losing Value",
        temporal_confidence="HIGH",
    )

    with (
        mock.patch("synckar.pipeline.dispatcher.resolve_conflict", return_value=conflict_record),
        mock.patch("synckar.pipeline.dispatcher._get_shop_client"),
        mock.patch("synckar.pipeline.dispatcher._get_factories_client"),
    ):
        event = _make_event(source_system=SourceSystem.SHOP_ESTABLISHMENT)
        results = dispatch_sws_to_departments(event)

    # Conflict record must be written (C5)
    patch_dispatcher_deps["conflict_record"].assert_called()
    # Loser must be skipped
    assert results["shop_establishment"]["reason"].startswith("conflict_")


def test_conflict_winner_proceeds_to_write(patch_dispatcher_deps):
    """
    When a conflict is detected and this event is the winner, it must proceed
    to write to the target system.
    """
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments
    from synckar.pipeline.conflict import ConflictWindowEntry, ResolutionPolicy
    from synckar.models.audit import ConflictAuditRecord
    from uuid import uuid4

    # Simulate an existing dept entry in the conflict window
    existing = ConflictWindowEntry(
        source_system="shop_establishment",
        broker_sequence=50,
        correlation_id=str(uuid4()),
        value="Dept Losing Value",
    )
    patch_dispatcher_deps["conflict"].check_and_register.return_value = existing

    # SWS is the winner
    conflict_record = ConflictAuditRecord(
        correlation_id=uuid4(),
        ubid="KA-TEST-0001",
        field="registered_address",
        source_a_system="shop_establishment",
        source_a_value="Dept Losing Value",
        source_b_system="sws",
        source_b_value="SWS Winning Value",
        policy_applied=ResolutionPolicy.SWS_WINS.value,
        winning_value="SWS Winning Value",
        losing_value="Dept Losing Value",
        temporal_confidence="HIGH",
    )

    with (
        mock.patch("synckar.pipeline.dispatcher.resolve_conflict", return_value=conflict_record),
        mock.patch("synckar.pipeline.dispatcher._get_shop_client") as mock_shop,
        mock.patch("synckar.pipeline.dispatcher._get_factories_client") as mock_fact,
        mock.patch("synckar.pipeline.dispatcher.shop_translate_outbound") as mock_shop_tx,
        mock.patch("synckar.pipeline.dispatcher.factories_translate_outbound") as mock_fact_tx,
    ):
        mock_shop_tx.return_value = {"Buss_Addr_Line1": "SWS Winning Value"}
        shop_client = mock.Mock()
        shop_client.update_record.return_value = {"updated_fields": ["Buss_Addr_Line1"]}
        mock_shop.return_value = shop_client

        mock_fact_tx.return_value = {"factory_address": "SWS Winning Value"}
        fact_client = mock.Mock()
        fact_client.update_record.return_value = {"updated_fields": ["factory_address"]}
        mock_fact.return_value = fact_client

        event = _make_event(source_system=SourceSystem.SWS, new_value="SWS Winning Value")
        results = dispatch_sws_to_departments(event)

    # Winner proceeds to write
    assert results["shop_establishment"]["status"] == "success"
    patch_dispatcher_deps["conflict_record"].assert_called()


def test_circuit_breaker_open_does_not_call_api_and_records_error(patch_dispatcher_deps):
    """
    When circuit breaker is OPEN, no API call is made.
    CircuitBreakerOpen is treated as a retriable error (same as TargetWriteError),
    so it is collected per-adapter and re-raised after all adapters are attempted.
    This means dispatch_sws_to_departments raises CircuitBreakerOpen.
    """
    from synckar.pipeline.dispatcher import dispatch_sws_to_departments
    from synckar.exceptions import CircuitBreakerOpen

    patch_dispatcher_deps["cb"].is_call_permitted.return_value = False

    with mock.patch("synckar.pipeline.dispatcher._get_shop_client") as mock_shop:
        shop_client = mock.Mock()
        mock_shop.return_value = shop_client

        event = _make_event()
        # CircuitBreakerOpen is re-raised after all adapters are attempted
        with pytest.raises(CircuitBreakerOpen):
            dispatch_sws_to_departments(event)

    # API must NOT have been called
    shop_client.update_record.assert_not_called()
