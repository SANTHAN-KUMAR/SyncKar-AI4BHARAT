"""DLQ management routes — list, resolve, stats."""

import json

import psycopg2.extras
import structlog
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from synckar.config import settings
from synckar import db

logger = structlog.get_logger()
router = APIRouter()


class DLQResolution(BaseModel):
    action: str  # "resolve" | "discard" | "retry"
    resolution_note: Optional[str] = None


@router.get("")
def list_dlq(status: str = "PENDING", limit: int = 50):
    """List DLQ items by status."""
    conn = db.get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT * FROM dead_letter_queue WHERE status = %s ORDER BY created_at DESC LIMIT %s",
        (status, limit),
    )
    rows = cursor.fetchall()
    db.put_conn(conn)

    results = []
    for row in rows:
        r = dict(row)
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            elif hasattr(v, "hex"):
                r[k] = str(v)
        results.append(r)

    return {"dlq_items": results, "count": len(results)}


@router.post("/{dlq_id}/resolve")
def resolve_dlq(dlq_id: str, resolution: DLQResolution):
    """Resolve or discard a DLQ item."""
    conn = db.get_conn()
    cursor = conn.cursor()

    new_status = "RESOLVED" if resolution.action == "resolve" else "DISCARDED"
    if resolution.action == "retry":
        cursor.execute(
            "SELECT raw_payload, source_system FROM dead_letter_queue WHERE id = %s::uuid",
            (dlq_id,),
        )
        row = cursor.fetchone()
        if not row:
            db.put_conn(conn)
            return {"error": "DLQ item not found", "id": dlq_id}

        raw_payload, source_system = row
        if isinstance(raw_payload, str):
            raw_payload = json.loads(raw_payload)
        from synckar.models.service_request import CanonicalServiceRequest
        from synckar.pipeline.outbox import write_to_outbox
        from synckar.pipeline.outbox import _resolve_topic

        event = CanonicalServiceRequest(**raw_payload)
        topic = _resolve_topic(source_system or event.source_system.value)
        write_to_outbox(event, topic=topic, conn=conn)

        cursor.execute(
            "UPDATE dead_letter_queue SET status = 'RETRIED', resolved_at = now() WHERE id = %s::uuid",
            (dlq_id,),
        )
        conn.commit()
        db.put_conn(conn)
        logger.info("dlq_retried", dlq_id=dlq_id)
        return {"id": dlq_id, "new_status": "RETRIED"}

    cursor.execute(
        "UPDATE dead_letter_queue SET status = %s, resolved_at = now() WHERE id = %s::uuid",
        (new_status, dlq_id),
    )
    affected = cursor.rowcount
    conn.commit()
    db.put_conn(conn)

    if affected == 0:
        return {"error": "DLQ item not found", "id": dlq_id}

    logger.info("dlq_resolved", dlq_id=dlq_id, action=resolution.action)
    return {"id": dlq_id, "new_status": new_status}


@router.get("/conflicts")
def list_conflicts(ubid: Optional[str] = None, limit: int = 50):
    """List conflict records, optionally filtered by UBID."""
    conn = db.get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    if ubid:
        cursor.execute(
            "SELECT * FROM conflict_log WHERE ubid = %s ORDER BY created_at DESC LIMIT %s",
            (ubid, limit),
        )
    else:
        cursor.execute(
            "SELECT * FROM conflict_log ORDER BY created_at DESC LIMIT %s",
            (limit,),
        )

    rows = cursor.fetchall()
    db.put_conn(conn)

    results = []
    for row in rows:
        r = dict(row)
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            elif hasattr(v, "hex"):
                r[k] = str(v)
        results.append(r)

    return {"conflicts": results, "count": len(results)}
