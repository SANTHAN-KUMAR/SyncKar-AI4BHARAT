"""Audit ledger query routes — search by UBID, correlation_id, end-to-end trace."""

import json

import structlog
from fastapi import APIRouter, Query
from typing import Optional

from synckar.config import settings
from synckar import db
import psycopg2.extras
from synckar.audit.signing import verify_signature

logger = structlog.get_logger()
router = APIRouter()


@router.get("")
def search_audit(
    ubid: Optional[str] = Query(default=None),
    correlation_id: Optional[str] = Query(default=None),
    after: Optional[str] = Query(default=None, description="Return rows created before this ISO timestamp"),
    limit: int = Query(default=50, le=200),
):
    """Search audit ledger by UBID and/or correlation_id."""
    conn = db.get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    conditions = []
    params = []

    if ubid:
        conditions.append("ubid = %s")
        params.append(ubid)
    if correlation_id:
        conditions.append("correlation_id = %s::uuid")
        params.append(correlation_id)
    if after:
        conditions.append("created_at < %s::timestamptz")
        params.append(after)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    params.append(limit)

    cursor.execute(
        f"SELECT * FROM audit_ledger {where} ORDER BY created_at DESC LIMIT %s",
        params,
    )
    rows = cursor.fetchall()
    db.put_conn(conn)

    # Convert UUIDs and datetimes to strings
    results = []
    for row in rows:
        r = dict(row)
        for k, v in r.items():
            if hasattr(v, "isoformat"):
                r[k] = v.isoformat()
            elif hasattr(v, "hex"):
                r[k] = str(v)
        results.append(r)

    return {"audit_entries": results, "count": len(results)}


@router.get("/trace/{correlation_id}")
def trace_request(correlation_id: str):
    """End-to-end trace of a single service request by correlation_id."""
    conn = db.get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT * FROM audit_ledger WHERE correlation_id = %s::uuid ORDER BY created_at",
        (correlation_id,),
    )
    audit_rows = cursor.fetchall()

    cursor.execute(
        "SELECT * FROM conflict_log WHERE correlation_id = %s::uuid ORDER BY created_at",
        (correlation_id,),
    )
    conflicts = cursor.fetchall()
    db.put_conn(conn)

    def serialize(rows):
        results = []
        for row in rows:
            r = dict(row)
            for k, v in r.items():
                if hasattr(v, "isoformat"):
                    r[k] = v.isoformat()
                elif hasattr(v, "hex"):
                    r[k] = str(v)
            results.append(r)
        return results

    return {
        "correlation_id": correlation_id,
        "audit_trail": serialize(audit_rows),
        "conflicts": serialize(conflicts),
        "hop_count": len(audit_rows),
    }


@router.get("/verify/{audit_id}")
def verify_audit_row(audit_id: str):
    """Verify RSA signature on an audit row (BSA 2023 compliance demo)."""
    conn = db.get_conn()
    cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

    cursor.execute(
        "SELECT * FROM audit_ledger WHERE audit_id = %s::uuid",
        (audit_id,),
    )
    row = cursor.fetchone()
    db.put_conn(conn)

    if not row:
        return {"error": "Audit row not found", "audit_id": audit_id}

    # Reconstruct the signed data
    row_data = json.dumps({
        "correlation_id": str(row["correlation_id"]),
        "ubid": row["ubid"],
        "field_modified": row["field_modified"],
        "old_value": row["old_value"],
        "new_value": row["new_value"],
        "source_system": row["source_system"],
        "target_system": row["target_system"],
        "payload_sha256": row["payload_sha256"],
    }, sort_keys=True)

    is_valid = verify_signature(row_data, row["rsa_signature"])

    return {
        "audit_id": audit_id,
        "signature_valid": is_valid,
        "payload_sha256": row["payload_sha256"],
        "bsa_2023_compliant": is_valid,
        "verification_details": {
            "ubid": row["ubid"],
            "field": row["field_modified"],
            "source": row["source_system"],
            "target": row["target_system"],
        },
    }
