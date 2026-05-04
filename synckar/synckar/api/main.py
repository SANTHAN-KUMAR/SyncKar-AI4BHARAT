"""
SyncKar API — FastAPI application.
Admin API, webhook receivers, audit search, DLQ management, health check.
The built React dashboard is served from /dashboard (StaticFiles).

Railway free-plan consolidation:
  - Celery worker and beat are started as daemon threads on startup so we
    don't need separate Railway services for them.
  - The three mock systems are served by a separate combined service
    (mock_systems/combined_app.py) to stay within the 4-service limit.
"""

import json
import os
import threading

import structlog
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from synckar.api.routes import webhooks, audit, dlq, health

logger = structlog.get_logger()

app = FastAPI(
    title="SyncKar — Interoperability Layer API",
    description="Event-driven interoperability layer for Karnataka SWS",
    version="0.1.0",
)

# CORS — allow all origins so the dashboard can call the API
# even when served from a different domain during development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(health.router, tags=["Health"])
app.include_router(audit.router, prefix="/api/audit", tags=["Audit"])
app.include_router(dlq.router, prefix="/api/dlq", tags=["DLQ"])
app.include_router(webhooks.router, prefix="/api/webhooks", tags=["Webhooks"])

# ─── Serve the built React dashboard ───
# The Dockerfile builds the dashboard into /app/dashboard/dist.
# In local dev, the dist folder may not exist — skip gracefully.
_DASHBOARD_DIST = os.path.join(os.path.dirname(__file__), "..", "..", "dashboard", "dist")
_DASHBOARD_DIST = os.path.abspath(_DASHBOARD_DIST)

if os.path.isdir(_DASHBOARD_DIST):
    # Serve static assets (JS, CSS, icons)
    app.mount(
        "/dashboard/assets",
        StaticFiles(directory=os.path.join(_DASHBOARD_DIST, "assets")),
        name="dashboard-assets",
    )

    @app.get("/dashboard/{full_path:path}", include_in_schema=False)
    async def serve_dashboard(full_path: str):
        """Serve the React SPA — all sub-paths return index.html."""
        index = os.path.join(_DASHBOARD_DIST, "index.html")
        return FileResponse(index)

    @app.get("/dashboard", include_in_schema=False)
    async def serve_dashboard_root():
        index = os.path.join(_DASHBOARD_DIST, "index.html")
        return FileResponse(index)

    logger.info("dashboard_serving_enabled", path=_DASHBOARD_DIST)
else:
    logger.info("dashboard_dist_not_found_skipping", expected=_DASHBOARD_DIST)


@app.on_event("startup")
async def startup():
    """
    Start background threads on API startup:
      1. Kafka consumer (dispatches events to Celery tasks)
      2. Celery worker  (processes propagation tasks)
      3. Celery beat    (runs polling schedules)

    All three run as daemon threads so they die cleanly when the process exits.
    This consolidates what would otherwise be three separate Railway services
    into one, staying within the free-plan 4-service limit.
    """
    logger.info("synckar_api_starting")
    _start_kafka_consumers()
    _start_celery_worker()
    _start_celery_beat()


def _start_kafka_consumers():
    """Start Kafka consumer threads for each topic. Auto-restarts on fatal error."""
    from synckar.config import settings
    from confluent_kafka import Consumer, KafkaError
    import time

    topics_to_consume = [
        settings.kafka.topic_sws_changes,
        settings.kafka.topic_dept_shop_changes,
        settings.kafka.topic_dept_factories_changes,
    ]

    def consumer_loop():
        """Consumer loop with automatic restart on fatal errors."""
        restart_delay = 5  # seconds between restart attempts
        while True:
            consumer = None
            try:
                conf = {
                    "bootstrap.servers": settings.kafka.bootstrap_servers,
                    "group.id": "synckar-dispatcher",
                    "auto.offset.reset": "earliest",
                    "enable.auto.commit": False,
                    # Heartbeat / session settings to detect dead consumers quickly
                    "session.timeout.ms": 30000,
                    "heartbeat.interval.ms": 10000,
                }
                if settings.kafka.security_protocol != "PLAINTEXT":
                    conf["security.protocol"] = settings.kafka.security_protocol
                if settings.kafka.sasl_mechanism:
                    conf["sasl.mechanism"] = settings.kafka.sasl_mechanism
                    conf["sasl.username"] = settings.kafka.sasl_username
                    conf["sasl.password"] = settings.kafka.sasl_password
                if settings.kafka.ssl_ca_path:
                    conf["ssl.ca.location"] = settings.kafka.ssl_ca_path

                consumer = Consumer(conf)
                consumer.subscribe(topics_to_consume)
                logger.info("kafka_consumer_started", topics=topics_to_consume)

                while True:
                    msg = consumer.poll(timeout=1.0)
                    if msg is None:
                        continue
                    if msg.error():
                        if msg.error().code() == KafkaError._PARTITION_EOF:
                            continue
                        logger.error("kafka_consumer_error", error=str(msg.error()))
                        continue

                    # Dispatch via Celery task (commit after completion)
                    from synckar.workers.celery_app import propagate_event_task

                    event_json = msg.value().decode("utf-8")
                    source_topic = msg.topic()
                    try:
                        event_data = json.loads(event_json)
                        event_data["broker_sequence"] = msg.offset()
                        event_json = json.dumps(event_data)
                    except Exception:
                        logger.warning("broker_sequence_set_failed")

                    result = propagate_event_task.apply_async(
                        args=[event_json, source_topic],
                        retry=False,
                    )

                    try:
                        result.get(timeout=settings.pipeline.consumer_task_timeout_seconds)
                        consumer.commit(asynchronous=False)
                    except Exception as e:
                        logger.error("celery_task_failed", error=str(e))
                        # No commit — Kafka will redeliver
                        continue

            except Exception as e:
                logger.error("kafka_consumer_fatal", error=str(e), restarting_in=restart_delay)
            finally:
                if consumer is not None:
                    try:
                        consumer.close()
                    except Exception:
                        pass

            # Wait before restarting to avoid tight restart loops
            time.sleep(restart_delay)

    thread = threading.Thread(target=consumer_loop, daemon=True, name="kafka-consumer")
    thread.start()


def _start_celery_worker():
    """
    Start an embedded Celery worker in a daemon thread.

    Uses solo pool (single-threaded) so it runs safely inside the same
    process as the FastAPI server without forking.  Concurrency is kept
    intentionally low — the worker only needs to handle propagation tasks
    that the Kafka consumer dispatches.
    """
    def _worker_loop():
        import time
        # Brief delay so the API is fully initialised before the worker starts
        time.sleep(3)
        try:
            from synckar.workers.celery_app import celery_app as _celery
            # solo pool = no subprocess fork; safe inside uvicorn's event loop process
            _celery.worker_main(
                argv=[
                    "worker",
                    "--loglevel=info",
                    "--pool=solo",
                    "--concurrency=1",
                    "--without-gossip",
                    "--without-mingle",
                    "--without-heartbeat",
                    "-n",
                    "embedded-worker@%h",
                ]
            )
        except Exception as e:
            logger.error("embedded_celery_worker_error", error=str(e))

    thread = threading.Thread(target=_worker_loop, daemon=True, name="celery-worker")
    thread.start()
    logger.info("embedded_celery_worker_started")


def _start_celery_beat():
    """
    Start an embedded Celery beat scheduler in a daemon thread.

    Beat writes its schedule state to /tmp/celerybeat-schedule so it
    doesn't need a writable project directory.
    """
    def _beat_loop():
        import time
        # Wait for worker to be ready before beat starts firing tasks
        time.sleep(6)
        try:
            from synckar.workers.celery_app import celery_app as _celery
            _celery.Beat(
                loglevel="info",
                schedule="/tmp/celerybeat-schedule",
            ).run()
        except Exception as e:
            logger.error("embedded_celery_beat_error", error=str(e))

    thread = threading.Thread(target=_beat_loop, daemon=True, name="celery-beat")
    thread.start()
    logger.info("embedded_celery_beat_started")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8080)
