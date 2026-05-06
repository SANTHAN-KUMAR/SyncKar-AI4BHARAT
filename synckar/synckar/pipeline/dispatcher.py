"""
Dispatcher — ARCHITECTURE.md §4 step 7, AGENTS.md §9 (C9).
Fan-out: for each event, determine target adapters and dispatch independently.
One adapter failing must NOT block other adapters (C9).
"""

import json

import structlog

from synckar.adapters.sws.client import SWSClient
from synckar.adapters.sws.translator import translate_outbound as sws_translate_outbound
from synckar.adapters.departments.shop_establishment.client import ShopEstablishmentClient
from synckar.adapters.departments.shop_establishment.translator import (
    translate_outbound as shop_translate_outbound,
)
from synckar.adapters.departments.factories.client import FactoriesClient
from synckar.adapters.departments.factories.translator import (
    translate_outbound as factories_translate_outbound,
)
from synckar.audit.ledger import write_audit_row, write_conflict_record
from synckar.exceptions import (
    TargetWriteError,
    PermanentWriteError,
    UBIDNotFound,
    TranslationError,
    CircuitBreakerOpen,
    IdempotencyKeyInProgress,
    RateLimitExceeded,
)
from synckar.models.service_request import CanonicalServiceRequest, make_idempotency_key
from synckar.pipeline.circuit_breaker import CircuitBreaker
from synckar.pipeline.conflict import (
    SlidingWindowConflictDetector,
    resolve_conflict,
    ResolutionPolicy,
)
from synckar.pipeline.idempotency import IdempotencyEngine, IdempotencyStatus
from synckar.config import settings
import redis
import time

logger = structlog.get_logger()

ADAPTER_TIERS = {
    "sws": 1,
    "shop_establishment": 1,
    "factories": 3,
}

# Singleton instances
_sws_client = None
_shop_client = None
_factories_client = None
_idempotency = None
_conflict_detector = None
_redis_client = None
_circuit_breakers: dict[str, CircuitBreaker] = {}

def _get_redis() -> redis.Redis:
    global _redis_client
    if not _redis_client:
        _redis_client = redis.Redis.from_url(settings.redis.url, decode_responses=True)
    return _redis_client

def _check_rate_limit(adapter_id: str, limit: int = 100, window_seconds: int = 60) -> bool:
    """Basic sliding window rate limiter."""
    r = _get_redis()
    key = f"rate_limit:{adapter_id}"
    now = int(time.time())
    member = f"{now}-{time.time_ns()}"
    
    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, now - window_seconds)
    pipe.zadd(key, {member: now})
    pipe.zcard(key)
    pipe.expire(key, window_seconds)
    results = pipe.execute()
    
    return results[2] <= limit


def _get_sws_client() -> SWSClient:
    global _sws_client
    if not _sws_client:
        _sws_client = SWSClient()
    return _sws_client


def _get_shop_client() -> ShopEstablishmentClient:
    global _shop_client
    if not _shop_client:
        _shop_client = ShopEstablishmentClient()
    return _shop_client


def _get_factories_client() -> FactoriesClient:
    global _factories_client
    if not _factories_client:
        _factories_client = FactoriesClient()
    return _factories_client


def _get_idempotency() -> IdempotencyEngine:
    global _idempotency
    if not _idempotency:
        _idempotency = IdempotencyEngine()
    return _idempotency


def _get_conflict_detector() -> SlidingWindowConflictDetector:
    global _conflict_detector
    if not _conflict_detector:
        _conflict_detector = SlidingWindowConflictDetector()
    return _conflict_detector


def _get_circuit_breaker(adapter_id: str) -> CircuitBreaker:
    if adapter_id not in _circuit_breakers:
        _circuit_breakers[adapter_id] = CircuitBreaker(adapter_id)
    return _circuit_breakers[adapter_id]


def _is_stale_event(event: CanonicalServiceRequest) -> bool:
    """Drop events that were generated before a hard reset but are still in Kafka."""
    r = _get_redis()
    reset_iso = r.get("hard_reset_timestamp")
    if reset_iso and event.received_at.isoformat() < reset_iso:
        return True
    return False


def dispatch_sws_to_departments(event: CanonicalServiceRequest) -> dict:
    """
    Fan-out an SWS change to all relevant department adapters.
    Each adapter is dispatched independently — one failure doesn't block others (C9).

    Returns a dict of {adapter_id: result_or_error}.

    Re-raises TargetWriteError and IdempotencyKeyInProgress so the Celery task
    can apply exponential-backoff retry.  All other per-adapter errors are caught
    and recorded so one adapter never blocks another (C9).
    """
    if _is_stale_event(event):
        logger.info("stale_event_dropped_sws_to_dept", ubid=event.ubid, received_at=event.received_at.isoformat())
        return {"status": "dropped", "reason": "hard_reset"}

    results = {}

    retriable_errors: list[Exception] = []

    # Dispatch to Shop Establishment
    try:
        results["shop_establishment"] = _propagate_to_adapter(
            event=event,
            adapter_id="shop_establishment",
            client=_get_shop_client(),
            translate_fn=shop_translate_outbound,
            update_fn=lambda ubid, fields: _get_shop_client().update_record(ubid, fields),
            api_endpoint_base="shop_establishment",
        )
    except (TargetWriteError, IdempotencyKeyInProgress, CircuitBreakerOpen, RateLimitExceeded) as e:
        retriable_errors.append(e)
        results["shop_establishment"] = {"error": str(e), "retriable": True}
    except Exception as e:
        results["shop_establishment"] = {"error": str(e)}
        logger.error("dispatch_shop_failed", ubid=event.ubid, error=str(e))

    # Dispatch to Factories
    try:
        results["factories"] = _propagate_to_adapter(
            event=event,
            adapter_id="factories",
            client=_get_factories_client(),
            translate_fn=factories_translate_outbound,
            update_fn=lambda ubid, fields: _get_factories_client().update_record(ubid, fields),
            api_endpoint_base="factories",
        )
    except (TargetWriteError, IdempotencyKeyInProgress, CircuitBreakerOpen, RateLimitExceeded) as e:
        retriable_errors.append(e)
        results["factories"] = {"error": str(e), "retriable": True}
    except Exception as e:
        results["factories"] = {"error": str(e)}
        logger.error("dispatch_factories_failed", ubid=event.ubid, error=str(e))

    if retriable_errors:
        # Trigger Celery retry after attempting all adapters
        raise retriable_errors[0]

    return results


def dispatch_department_to_sws(event: CanonicalServiceRequest) -> dict:
    """
    Propagate a department change to SWS.
    Re-raises TargetWriteError / IdempotencyKeyInProgress for Celery retry.
    """
    if _is_stale_event(event):
        logger.info("stale_event_dropped_dept_to_sws", ubid=event.ubid, received_at=event.received_at.isoformat())
        return {"status": "dropped", "reason": "hard_reset"}

    results = {}
    try:
        results["sws"] = _propagate_to_adapter(
            event=event,
            adapter_id="sws",
            client=_get_sws_client(),
            translate_fn=sws_translate_outbound,
            update_fn=lambda ubid, fields: _get_sws_client().update_business(ubid, fields),
            api_endpoint_base="sws",
        )
    except (TargetWriteError, IdempotencyKeyInProgress, CircuitBreakerOpen, RateLimitExceeded):
        raise
    except Exception as e:
        results["sws"] = {"error": str(e)}
        logger.error("dispatch_sws_failed", ubid=event.ubid, error=str(e))

    return results


def _propagate_to_adapter(
    event: CanonicalServiceRequest,
    adapter_id: str,
    client,
    translate_fn,
    update_fn,
    api_endpoint_base: str,
) -> dict:
    """
    Full propagation pipeline for a single target adapter.
    Steps: rate limit → circuit breaker → conflict detection → idempotency → translate → write → audit.
    """
    # 0. Rate limit check (e.g., 100 requests per minute)
    if not _check_rate_limit(adapter_id, limit=100, window_seconds=60):
        logger.warning("rate_limit_exceeded", adapter=adapter_id, ubid=event.ubid)
        raise RateLimitExceeded(
            f"Rate limit exceeded for {adapter_id}",
            system_id=adapter_id,
            ubid=event.ubid,
        )

    # 1. Circuit breaker check
    cb = _get_circuit_breaker(adapter_id)
    if not cb.is_call_permitted():
        logger.warning("circuit_breaker_open", adapter=adapter_id, ubid=event.ubid)
        raise CircuitBreakerOpen(
            f"Circuit breaker OPEN for {adapter_id}",
            system_id=adapter_id,
            ubid=event.ubid,
        )

    # 2. Conflict detection
    detector = _get_conflict_detector()
    existing = detector.check_and_register(event)

    conflict_detected = False
    resolution_policy = None
    temporal_conf = None

    if existing:
        conflict_detected = True
        incoming_tier = ADAPTER_TIERS.get(event.source_system.value, 3)
        existing_tier = ADAPTER_TIERS.get(existing.source_system, 3)
        conflict_record = resolve_conflict(
            event,
            existing,
            incoming_tier=incoming_tier,
            existing_tier=existing_tier,
        )
        write_conflict_record(conflict_record)

        resolution_policy = conflict_record.policy_applied
        temporal_conf = conflict_record.temporal_confidence

        if conflict_record.policy_applied == ResolutionPolicy.DLQ.value:
            logger.info("conflict_dlq", ubid=event.ubid, field=event.field_name)
            # Write audit row for DLQ routing
            write_audit_row(
                event=event,
                target_system=adapter_id,
                api_endpoint=f"{api_endpoint_base}/dlq",
                conflict_detected=True,
                resolution_policy="DLQ",
                temporal_confidence=temporal_conf,
            )
            return {"status": "DLQ", "reason": "unmapped_field_conflict"}

        # Check if this event is the loser
        if conflict_record.winning_value != event.new_value:
            logger.info(
                "conflict_loser_skipped",
                ubid=event.ubid,
                field=event.field_name,
                policy=resolution_policy,
            )
            write_audit_row(
                event=event,
                target_system=adapter_id,
                api_endpoint=f"{api_endpoint_base}/skipped",
                conflict_detected=True,
                resolution_policy=resolution_policy,
                broker_seq_a=existing.broker_sequence,
                broker_seq_b=event.broker_sequence,
                temporal_confidence=temporal_conf,
            )
            return {"status": "skipped", "reason": f"conflict_{resolution_policy}"}

    # 3. Idempotency check
    idem_key = make_idempotency_key(
        source_system_id=event.source_system.value,
        source_event_id=event.source_event_id,
        ubid=event.ubid,
        field_name=event.field_name,
        new_value=event.new_value,
    )
    # Ensure idempotency is checked per-target adapter so one adapter doesn't block another
    idem_key = f"{idem_key}:{adapter_id}"

    idem_engine = _get_idempotency()
    status, cached = idem_engine.reserve(idem_key)

    if status == IdempotencyStatus.COMPLETED:
        logger.info("idempotency_skip", ubid=event.ubid, adapter=adapter_id)
        return {"status": "skipped", "reason": "already_completed"}

    try:
        # 4. Translate outbound
        native_payload = translate_fn(event)

        # Redis down fallback — compare target state and skip if already matches
        if status == IdempotencyStatus.NOT_FOUND:
            target_field = next(
                (k for k in native_payload.keys() if k != "modified_by"),
                event.field_name,
            )
            try:
                if adapter_id == "sws":
                    current = client.get_business(event.ubid)
                else:
                    current = client.get_record(event.ubid)
                current_value = str((current or {}).get(target_field, ""))
                desired_value = str(native_payload.get(target_field, ""))
                if current and current_value == desired_value:
                    write_audit_row(
                        event=event,
                        target_system=adapter_id,
                        api_endpoint=f"{api_endpoint_base}/skipped",
                        conflict_detected=conflict_detected,
                        resolution_policy="IDEMPOTENCY_FALLBACK_SKIP",
                        broker_seq_a=existing.broker_sequence if existing else None,
                        broker_seq_b=event.broker_sequence,
                        temporal_confidence=temporal_conf,
                    )
                    return {"status": "skipped", "reason": "target_already_matches"}
            except Exception:
                pass

        # 5. Write to target system
        try:
            result = update_fn(event.ubid, native_payload)
            cb.record_success()
        except UBIDNotFound:
            idem_engine.release(idem_key)
            logger.info("ubid_not_found_skip", ubid=event.ubid, adapter=adapter_id)
            return {"status": "skipped", "reason": "ubid_not_found"}
        except TargetWriteError:
            cb.record_failure()
            idem_engine.release(idem_key)
            raise
        except PermanentWriteError:
            idem_engine.release(idem_key)
            write_audit_row(
                event=event,
                target_system=adapter_id,
                api_endpoint=f"{api_endpoint_base}/failed",
                conflict_detected=conflict_detected,
                resolution_policy="FAILED_4XX",
                broker_seq_a=existing.broker_sequence if existing else None,
                broker_seq_b=event.broker_sequence,
                temporal_confidence=temporal_conf,
            )
            raise

        # 6. Mark idempotency as COMPLETED
        idem_engine.complete(idem_key)

        # 7. Write audit row (C5: every write produces an audit row)
        api_endpoint = f"{api_endpoint_base}/api/records/by-ubid/{event.ubid}"
        write_audit_row(
            event=event,
            target_system=adapter_id,
            api_endpoint=api_endpoint,
            conflict_detected=conflict_detected,
            resolution_policy=resolution_policy,
            broker_seq_a=existing.broker_sequence if existing else None,
            broker_seq_b=event.broker_sequence,
            temporal_confidence=temporal_conf,
        )

        logger.info(
            "propagation_success",
            ubid=event.ubid,
            source=event.source_system.value,
            target=adapter_id,
            field=event.field_name,
        )
        try:
            from synckar.pipeline import loop_guard
            loop_guard.mark_write(adapter_id, event.ubid, event.field_name, event.new_value)
        except Exception:
            pass
        return {"status": "success", "target": adapter_id}

    except (TargetWriteError, PermanentWriteError):
        raise
    except Exception as e:
        idem_engine.release(idem_key)
        logger.error("propagation_error", ubid=event.ubid, adapter=adapter_id, error=str(e))
        raise
