"""
Transactional Outbox — ARCHITECTURE.md §4 step 4, §5 step 4.
Atomic write to PostgreSQL; drains to Kafka when available.

If Kafka is unavailable, events stay in the outbox table (status=PENDING)
and are drained on reconnect. This guarantees at-least-once delivery
even during network partitions (Solution §10, Failure #6).
"""

import json
from uuid import UUID

import structlog
from confluent_kafka import Producer, KafkaError

from synckar.config import settings
from synckar import db
from synckar.models.service_request import CanonicalServiceRequest

logger = structlog.get_logger()


def _get_db_connection():
    """Get a PostgreSQL connection from config."""
    return db.get_conn()


def _get_kafka_producer() -> Producer:
    """Create a Kafka producer with config from settings."""
    conf = {
        "bootstrap.servers": settings.kafka.bootstrap_servers,
    }
    if settings.kafka.security_protocol != "PLAINTEXT":
        conf["security.protocol"] = settings.kafka.security_protocol
    if settings.kafka.sasl_mechanism:
        conf["sasl.mechanism"] = settings.kafka.sasl_mechanism
        conf["sasl.username"] = settings.kafka.sasl_username
        conf["sasl.password"] = settings.kafka.sasl_password
    if settings.kafka.ssl_ca_path:
        conf["ssl.ca.location"] = settings.kafka.ssl_ca_path
    return Producer(conf)


def write_to_outbox(
    event: CanonicalServiceRequest,
    topic: str,
    conn=None,
) -> UUID:
    """
    Write a CanonicalServiceRequest to the Transactional Outbox.
    Returns the outbox entry ID.

    Uses an existing connection if provided (for atomicity with
    other writes in the same transaction), otherwise creates one.
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_db_connection()

    try:
        cursor = conn.cursor()
        outbox_id_query = """
            INSERT INTO outbox (
                correlation_id, ubid, source_system, event_type, payload,
                target_topic, status
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'PENDING')
            RETURNING id
        """
        payload = event.model_dump_json()
        cursor.execute(
            outbox_id_query,
            (
                str(event.correlation_id),
                event.ubid,
                event.source_system.value,
                event.request_type.value,
                payload,
                topic,
            ),
        )
        outbox_id = cursor.fetchone()[0]

        if own_conn:
            conn.commit()

        logger.info(
            "outbox_write",
            outbox_id=str(outbox_id),
            ubid=event.ubid,
            correlation_id=str(event.correlation_id),
            topic=topic,
        )
        return outbox_id

    except Exception:
        if own_conn:
            conn.rollback()
        raise
    finally:
        if own_conn:
            db.put_conn(conn)


def drain_outbox(batch_size: int = 50) -> int:
    """
    Drain PENDING events from the outbox to Kafka.
    Returns the number of events successfully delivered.

    This is called by a Celery periodic task. If Kafka is unavailable,
    events stay PENDING and will be drained on the next cycle.
    """
    conn = _get_db_connection()
    drained = 0

    try:
        producer = _get_kafka_producer()
    except Exception as e:
        logger.error("kafka_producer_init_failed", error=str(e))
        db.put_conn(conn)
        return 0

    # Track which outbox IDs were successfully delivered by Kafka callbacks
    delivered_ids: list = []
    failed_ids: list = []

    def _make_delivery_callback(outbox_id):
        def _cb(err, msg):
            if err:
                logger.error(
                    "kafka_delivery_failed",
                    outbox_id=str(outbox_id),
                    error=str(err),
                )
                failed_ids.append(outbox_id)
            else:
                logger.info(
                    "kafka_delivered",
                    outbox_id=str(outbox_id),
                    topic=msg.topic(),
                    partition=msg.partition(),
                    offset=msg.offset(),
                )
                delivered_ids.append(outbox_id)
        return _cb

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, payload, ubid, source_system, target_topic
            FROM outbox
            WHERE status = 'PENDING'
            ORDER BY created_at
            LIMIT %s
            FOR UPDATE SKIP LOCKED
            """,
            (batch_size,),
        )
        rows = cursor.fetchall()

        for row in rows:
            outbox_id, payload_str, ubid, source_system, target_topic = row

            # Determine the correct Kafka topic (prefer explicit target_topic)
            topic = target_topic or _resolve_topic(source_system)

            try:
                # Publish to Kafka with UBID as partition key
                # (ensures per-business ordering — ARCHITECTURE.md §4 step 5)
                producer.produce(
                    topic=topic,
                    key=ubid.encode("utf-8"),
                    value=payload_str.encode("utf-8") if isinstance(payload_str, str) else json.dumps(payload_str).encode("utf-8"),
                    callback=_make_delivery_callback(outbox_id),
                )
                producer.poll(0)

            except Exception as e:
                logger.error(
                    "outbox_publish_failed",
                    outbox_id=str(outbox_id),
                    error=str(e),
                )
                # Leave as PENDING — will be retried on next drain cycle
                continue

        # Wait for all outstanding Kafka deliveries (blocks until all callbacks fire)
        producer.flush(timeout=10)

        # Mark only successfully delivered events as PUBLISHED
        drained = len(delivered_ids)
        if drained > 0:
            placeholders = ",".join(["%s"] * len(delivered_ids))
            cursor.execute(
                f"UPDATE outbox SET status = 'PUBLISHED' WHERE id IN ({placeholders})",
                delivered_ids,
            )
            conn.commit()

        if failed_ids:
            logger.warning("outbox_drain_partial_failure", failed_count=len(failed_ids))

        logger.info("outbox_drained", count=drained)
        return drained

    except Exception as e:
        conn.rollback()
        logger.error("outbox_drain_error", error=str(e))
        return 0
    finally:
        db.put_conn(conn)


def _resolve_topic(source_system: str) -> str:
    """Map source system to the correct Kafka topic."""
    topic_map = {
        "sws": settings.kafka.topic_sws_changes,
        "shop_establishment": settings.kafka.topic_dept_shop_changes,
        "factories": settings.kafka.topic_dept_factories_changes,
    }
    return topic_map.get(source_system, settings.kafka.topic_sws_changes)
