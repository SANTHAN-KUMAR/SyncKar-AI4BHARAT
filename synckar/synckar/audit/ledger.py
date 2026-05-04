"""
Audit Ledger Writer — AGENTS.md §11, ARCHITECTURE.md §10.
Append-only PostgreSQL table. INSERT only — never UPDATE or DELETE (C6).

Every audit row includes:
  - SHA-256 hash of the full serialised CanonicalServiceRequest
  - RSA signature for tamper evidence (BSA 2023)
  - Losing conflict values are always preserved (C5)
  - All hops share the same correlation_id
"""

import hashlib
import json
from uuid import UUID

import structlog

from synckar.config import settings
from synckar.audit.signing import sign_audit_row
from synckar import db
from synckar.models.audit import AuditRow, ConflictAuditRecord
from synckar.models.service_request import CanonicalServiceRequest

logger = structlog.get_logger()


def _get_db_connection():
    return db.get_conn()


def compute_payload_sha256(event: CanonicalServiceRequest) -> str:
    """SHA-256 of the full serialised CanonicalServiceRequest JSON."""
    payload_json = event.model_dump_json(exclude_none=False)
    return hashlib.sha256(payload_json.encode()).hexdigest()


def write_audit_row(
    event: CanonicalServiceRequest,
    target_system: str,
    api_endpoint: str,
    source_ip: str = "127.0.0.1",
    conflict_detected: bool = False,
    resolution_policy: str | None = None,
    broker_seq_a: int | None = None,
    broker_seq_b: int | None = None,
    temporal_confidence: str | None = None,
    conn=None,
) -> UUID:
    """
    Write a single audit row to the append-only ledger.
    Returns the audit_id.

    INVARIANTS:
    - INSERT only — never UPDATE or DELETE (C6, enforced at DB level).
    - SHA-256 of full payload for integrity verification.
    - RSA signature for tamper evidence.
    """
    payload_sha256 = compute_payload_sha256(event)

    # Build the row data string for RSA signing
    row_data = json.dumps({
        "correlation_id": str(event.correlation_id),
        "ubid": event.ubid,
        "field_modified": event.field_name,
        "old_value": event.old_value,
        "new_value": event.new_value,
        "source_system": event.source_system.value,
        "target_system": target_system,
        "payload_sha256": payload_sha256,
    }, sort_keys=True)

    rsa_signature = sign_audit_row(row_data)

    own_conn = conn is None
    if own_conn:
        conn = _get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_ledger (
                correlation_id, ubid, field_modified, old_value, new_value,
                source_system, target_system, api_endpoint, source_ip,
                conflict_detected, resolution_policy,
                broker_seq_a, broker_seq_b, temporal_confidence,
                payload_sha256, rsa_signature
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s
            )
            RETURNING audit_id
            """,
            (
                str(event.correlation_id),
                event.ubid,
                event.field_name,
                event.old_value,
                event.new_value,
                event.source_system.value,
                target_system,
                api_endpoint,
                source_ip,
                conflict_detected,
                resolution_policy,
                broker_seq_a,
                broker_seq_b,
                temporal_confidence,
                payload_sha256,
                rsa_signature,
            ),
        )
        audit_id = cursor.fetchone()[0]

        if own_conn:
            conn.commit()

        logger.info(
            "audit_row_written",
            audit_id=str(audit_id),
            ubid=event.ubid,
            correlation_id=str(event.correlation_id),
            field=event.field_name,
            conflict=conflict_detected,
        )
        return audit_id

    except Exception:
        if own_conn:
            conn.rollback()
        raise
    finally:
        if own_conn:
            db.put_conn(conn)


def write_conflict_record(
    record: ConflictAuditRecord,
    conn=None,
) -> None:
    """
    Write a conflict audit record to the conflict_log table.
    Both winning and losing values are always preserved (C5).
    """
    own_conn = conn is None
    if own_conn:
        conn = _get_db_connection()

    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO conflict_log (
                correlation_id, ubid, field,
                source_a, source_b,
                policy_applied, winning_value, losing_value,
                temporal_confidence
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                str(record.correlation_id),
                record.ubid,
                record.field,
                json.dumps({
                    "system": record.source_a_system,
                    "value": record.source_a_value,
                    "broker_seq": record.source_a_broker_seq,
                }),
                json.dumps({
                    "system": record.source_b_system,
                    "value": record.source_b_value,
                    "broker_seq": record.source_b_broker_seq,
                }),
                record.policy_applied,
                record.winning_value,
                record.losing_value,
                record.temporal_confidence,
            ),
        )
        if own_conn:
            conn.commit()

        logger.info(
            "conflict_record_written",
            ubid=record.ubid,
            field=record.field,
            policy=record.policy_applied,
        )
    except Exception:
        if own_conn:
            conn.rollback()
        raise
    finally:
        if own_conn:
            db.put_conn(conn)
