"""
Celery application and worker tasks — AGENTS.md §4.
Polling, propagation, outbox drain, and reconciliation tasks.
"""

from celery import Celery
from celery.schedules import crontab
import structlog

from synckar.config import settings

logger = structlog.get_logger()

# ─── Celery App ───
celery_app = Celery(
    "synckar",
    broker=settings.celery.broker_url,
    backend=settings.celery.result_backend,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_hijack_root_logger=False,
    task_acks_late=True,
    task_reject_on_worker_lost=True,
)

# ─── Beat Schedule ───
celery_app.conf.beat_schedule = {
    "drain-outbox": {
        "task": "synckar.workers.celery_app.drain_outbox_task",
        "schedule": 3.0,  # Every 3 seconds
    },
    "poll-sws": {
        "task": "synckar.workers.celery_app.poll_sws_task",
        "schedule": float(settings.polling.sws_poll_interval_seconds),
    },
    "poll-shop": {
        "task": "synckar.workers.celery_app.poll_shop_task",
        "schedule": float(settings.polling.shop_poll_interval_seconds),
    },
    "poll-factories": {
        "task": "synckar.workers.celery_app.poll_factories_task",
        "schedule": float(settings.polling.factories_poll_interval_seconds),
    },
    "reconcile-nightly": {
        "task": "synckar.workers.reconciliation.reconcile_sample",
        "schedule": crontab(minute=0, hour=0),  # Run at midnight UTC
        "kwargs": {"sample_size": 20},
    },
    "probe-circuit-breakers": {
        "task": "synckar.workers.celery_app.probe_circuit_breakers_task",
        "schedule": float(settings.pipeline.circuit_breaker_probe_interval_seconds),
    },
}


# ─── Tasks ───

@celery_app.task(name="synckar.workers.celery_app.drain_outbox_task")
def drain_outbox_task():
    """Drain pending events from outbox to Kafka."""
    from synckar.pipeline.outbox import drain_outbox
    try:
        count = drain_outbox()
        if count > 0:
            logger.info("outbox_drained_by_worker", count=count)
    except Exception as e:
        logger.error("outbox_drain_task_error", error=str(e))


@celery_app.task(name="synckar.workers.celery_app.poll_sws_task")
def poll_sws_task():
    """Poll SWS for changes and write to outbox."""
    from synckar.adapters.sws.poller import SWSPoller
    from synckar.pipeline.outbox import write_to_outbox

    try:
        poller = SWSPoller()
        events = poller.poll()
        for event in events:
            write_to_outbox(event, topic="sws.changes")
        if events:
            logger.info("sws_polled", events=len(events))
    except Exception as e:
        logger.error("sws_poll_task_error", error=str(e))


@celery_app.task(name="synckar.workers.celery_app.poll_shop_task")
def poll_shop_task():
    """Poll Shop Establishment for changes and write to outbox."""
    from synckar.adapters.departments.shop_establishment.poller import ShopEstablishmentPoller
    from synckar.pipeline.outbox import write_to_outbox

    try:
        poller = ShopEstablishmentPoller()
        events = poller.poll()
        for event in events:
            write_to_outbox(event, topic="dept.shop_establishment.changes")
        if events:
            logger.info("shop_polled", events=len(events))
    except Exception as e:
        logger.error("shop_poll_task_error", error=str(e))


@celery_app.task(name="synckar.workers.celery_app.poll_factories_task")
def poll_factories_task():
    """Poll Factories for changes and write to outbox."""
    from synckar.adapters.departments.factories.poller import FactoriesPoller
    from synckar.pipeline.outbox import write_to_outbox

    try:
        poller = FactoriesPoller()
        events = poller.poll()
        for event in events:
            write_to_outbox(event, topic="dept.factories.changes")
        if events:
            logger.info("factories_polled", events=len(events))
    except Exception as e:
        logger.error("factories_poll_task_error", error=str(e))


@celery_app.task(name="synckar.workers.celery_app.probe_circuit_breakers_task")
def probe_circuit_breakers_task():
    """Attempt HALF_OPEN transition for any OPEN circuit breakers."""
    from synckar.pipeline.circuit_breaker import CircuitBreaker

    adapter_ids = ["sws", "shop_establishment", "factories"]
    for adapter_id in adapter_ids:
        try:
            cb = CircuitBreaker(adapter_id)
            cb.attempt_half_open()
        except Exception as e:
            logger.error("circuit_breaker_probe_error", adapter=adapter_id, error=str(e))


@celery_app.task(
    name="synckar.workers.celery_app.propagate_event_task",
    bind=True,
    max_retries=10,
    default_retry_delay=2,
)
def propagate_event_task(self, event_json: str, source_topic: str):
    """
    Propagate an event from Kafka to target adapters.
    Retry with exponential backoff on TargetWriteError or IdempotencyKeyInProgress.
    DLQ on PermanentWriteError.
    """
    import json
    from synckar.models.service_request import CanonicalServiceRequest
    from synckar.pipeline.dispatcher import (
        dispatch_sws_to_departments,
        dispatch_department_to_sws,
    )
    from synckar.exceptions import (
        TargetWriteError,
        PermanentWriteError,
        IdempotencyKeyInProgress,
        CircuitBreakerOpen,
    )

    try:
        event_data = json.loads(event_json)
        event = CanonicalServiceRequest(**event_data)

        if source_topic.startswith("sws."):
            results = dispatch_sws_to_departments(event)
        else:
            results = dispatch_department_to_sws(event)

        logger.info("propagation_complete", ubid=event.ubid, results=results)
        return results

    except IdempotencyKeyInProgress as e:
        # Another worker is live on this event — back off and retry
        backoff = min(
            settings.pipeline.retry_backoff_base_seconds * (2 ** self.request.retries),
            settings.pipeline.retry_backoff_max_seconds,
        )
        logger.warning(
            "propagation_idem_retry",
            attempt=self.request.retries + 1,
            backoff=backoff,
            error=str(e),
        )
        raise self.retry(exc=e, countdown=backoff)

    except (TargetWriteError, CircuitBreakerOpen) as e:
        # Exponential backoff retry — AGENTS.md §10
        backoff = min(
            settings.pipeline.retry_backoff_base_seconds * (2 ** self.request.retries),
            settings.pipeline.retry_backoff_max_seconds,
        )
        logger.warning(
            "propagation_retry",
            ubid=e.ubid,
            attempt=self.request.retries + 1,
            backoff=backoff,
        )
        raise self.retry(exc=e, countdown=backoff)

    except PermanentWriteError as e:
        # DLQ — no retry for 4xx errors
        logger.error("propagation_permanent_failure", ubid=e.ubid, status=e.status_code)
        _write_to_dlq(event_json, str(e), source_topic)

    except Exception as e:
        logger.error("propagation_unexpected_error", error=str(e))
        _write_to_dlq(event_json, str(e), source_topic)


def _write_to_dlq(event_json: str, error_reason: str, source_topic: str):
    """
    Write failed event to DLQ table AND write an audit row with status=DLQ.
    Re-raises on failure so Celery retries rather than silently losing the event.
    """
    import json
    from synckar import db

    try:
        event_data = json.loads(event_json)
        conn = db.get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO dead_letter_queue (correlation_id, ubid, raw_payload, error_reason, source_system, status)
                VALUES (%s, %s, %s, %s, %s, 'PENDING')
                """,
                (
                    event_data.get("correlation_id"),
                    event_data.get("ubid"),
                    json.dumps(event_data),
                    error_reason,
                    event_data.get("source_system"),
                ),
            )
            conn.commit()
        finally:
            db.put_conn(conn)

        # Write audit row so every propagation attempt is traceable (C5)
        try:
            from synckar.models.service_request import CanonicalServiceRequest
            from synckar.audit.ledger import write_audit_row
            event = CanonicalServiceRequest(**event_data)
            write_audit_row(
                event=event,
                target_system="dlq",
                api_endpoint="dlq/permanent_failure",
                conflict_detected=False,
                resolution_policy="DLQ_PERMANENT_FAILURE",
            )
        except Exception as audit_err:
            logger.warning("dlq_audit_row_failed", error=str(audit_err))

        logger.info("dlq_written", ubid=event_data.get("ubid"))
    except Exception as e:
        logger.error("dlq_write_failed", error=str(e))
        # Re-raise so Celery retries rather than silently dropping the event
        raise
