"""
Mock Systems Proxy — forwards browser requests to the mock-systems container.

The dashboard is served from the synckar-api container. The browser cannot
reach http://mock-systems:8000 directly (Docker internal DNS). This proxy
forwards /api/mock/* requests to the mock-systems container so the dashboard
can read and write mock system data from a single origin.

Routes:
  GET  /api/mock/{system}/businesses          → list all (SWS)
  GET  /api/mock/{system}/record/{ubid}       → get record by UBID
  PUT  /api/mock/{system}/record/{ubid}       → update record by UBID
  POST /api/mock/seed                         → seed all mock systems with 20 businesses
  POST /api/mock/reset                        → clear + reseed all mock systems
"""

import httpx
import structlog
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from synckar.config import settings

logger = structlog.get_logger()
router = APIRouter()

# ── Seed data — 20 Karnataka businesses ───────────────────────────────────────
# Embedded here so the proxy can seed/reset without importing seed_data.py
_SEED_BUSINESSES = [
    {"ubid": "KA-TEST-0001", "business_name": "Bengaluru Silk Weavers Pvt Ltd", "registered_address": "14 Cunningham Road, Bengaluru 560052", "primary_contact": "+91-80-4112-3456", "authorized_signatory": "Rajesh Kumar Sharma", "employee_headcount": 85, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-01-15"},
    {"ubid": "KA-TEST-0002", "business_name": "Mysuru Agro Industries Ltd", "registered_address": "Plot 22, KIADB Industrial Area, Mysuru 570016", "primary_contact": "+91-821-2412-789", "authorized_signatory": "Priya Venkatesh", "employee_headcount": 142, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-02-10"},
    {"ubid": "KA-TEST-0003", "business_name": "Hubli Steel Fabricators Pvt Ltd", "registered_address": "Survey No. 45, Gokul Road, Hubballi 580030", "primary_contact": "+91-836-2234-567", "authorized_signatory": "Suresh Basavaraj", "employee_headcount": 210, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-01-28"},
    {"ubid": "KA-TEST-0004", "business_name": "Mangaluru Cashew Exports Ltd", "registered_address": "Bunder Road, Mangaluru 575001", "primary_contact": "+91-824-2441-234", "authorized_signatory": "Anitha D'Souza", "employee_headcount": 67, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-03-05"},
    {"ubid": "KA-TEST-0005", "business_name": "Dharwad Pharma Solutions Pvt Ltd", "registered_address": "KSSIDC Industrial Estate, Dharwad 580004", "primary_contact": "+91-836-2448-901", "authorized_signatory": "Dr. Kavitha Patil", "employee_headcount": 320, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-02-20"},
    {"ubid": "KA-TEST-0006", "business_name": "Belagavi Textile Mills Ltd", "registered_address": "Udyambag Industrial Area, Belagavi 590008", "primary_contact": "+91-831-2423-678", "authorized_signatory": "Mahesh Kulkarni", "employee_headcount": 450, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-01-10"},
    {"ubid": "KA-TEST-0007", "business_name": "Tumkur Auto Components Pvt Ltd", "registered_address": "KIADB Phase II, Tumakuru 572106", "primary_contact": "+91-816-2272-345", "authorized_signatory": "Ravi Shankar Gowda", "employee_headcount": 178, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-03-12"},
    {"ubid": "KA-TEST-0008", "business_name": "Shivamogga Paper Industries Ltd", "registered_address": "Bhadravathi Road, Shivamogga 577201", "primary_contact": "+91-8182-223456", "authorized_signatory": "Lakshmi Narayana", "employee_headcount": 290, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-02-05"},
    {"ubid": "KA-TEST-0009", "business_name": "Kolar Gold Jewellers Pvt Ltd", "registered_address": "B B Road, Kolar 563101", "primary_contact": "+91-8152-222789", "authorized_signatory": "Srinivas Reddy", "employee_headcount": 45, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-01-22"},
    {"ubid": "KA-TEST-0010", "business_name": "Raichur Power Equipment Ltd", "registered_address": "Industrial Area, Raichur 584101", "primary_contact": "+91-8532-226789", "authorized_signatory": "Abdul Kareem", "employee_headcount": 520, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-03-01"},
    {"ubid": "KA-TEST-0011", "business_name": "Bidar Ceramics Pvt Ltd", "registered_address": "Udgir Road, Bidar 585401", "primary_contact": "+91-8482-227890", "authorized_signatory": "Fatima Begum", "employee_headcount": 95, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-02-15"},
    {"ubid": "KA-TEST-0012", "business_name": "Vijayapura Sugar Mills Ltd", "registered_address": "Solapur Road, Vijayapura 586101", "primary_contact": "+91-8352-250123", "authorized_signatory": "Basavaraj Patil", "employee_headcount": 680, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-01-05"},
    {"ubid": "KA-TEST-0013", "business_name": "Gadag Granite Exports Pvt Ltd", "registered_address": "NH-67, Gadag 582101", "primary_contact": "+91-8372-234567", "authorized_signatory": "Veeranna Hiremath", "employee_headcount": 130, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-03-18"},
    {"ubid": "KA-TEST-0014", "business_name": "Koppal Iron & Steel Ltd", "registered_address": "Gangavathi Road, Koppal 583231", "primary_contact": "+91-8539-220456", "authorized_signatory": "Nagaraj Bellad", "employee_headcount": 410, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-02-28"},
    {"ubid": "KA-TEST-0015", "business_name": "Yadgir Cement Works Pvt Ltd", "registered_address": "Gulbarga Road, Yadgir 585201", "primary_contact": "+91-8473-221789", "authorized_signatory": "Chandrashekhar Rao", "employee_headcount": 750, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-01-30"},
    {"ubid": "KA-TEST-0016", "business_name": "Bengaluru IT Solutions Pvt Ltd", "registered_address": "Whitefield, Bengaluru 560066", "primary_contact": "+91-80-4567-8901", "authorized_signatory": "Deepa Krishnamurthy", "employee_headcount": 230, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-03-10"},
    {"ubid": "KA-TEST-0017", "business_name": "Mysuru Handicrafts Emporium", "registered_address": "Sayyaji Rao Road, Mysuru 570001", "primary_contact": "+91-821-2423-456", "authorized_signatory": "Geetha Nagaraj", "employee_headcount": 38, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-02-22"},
    {"ubid": "KA-TEST-0018", "business_name": "Mangaluru Seafood Processors Ltd", "registered_address": "Panambur, Mangaluru 575010", "primary_contact": "+91-824-2456-789", "authorized_signatory": "Peter Fernandes", "employee_headcount": 165, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-01-18"},
    {"ubid": "KA-TEST-0019", "business_name": "Bengaluru Fintech Ventures Pvt Ltd", "registered_address": "Koramangala, Bengaluru 560034", "primary_contact": "+91-80-4890-1234", "authorized_signatory": "Arun Mehta", "employee_headcount": 55, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-03-20"},
    {"ubid": "KA-TEST-0020", "business_name": "Karnataka Organic Farms Ltd", "registered_address": "Hesaraghatta Road, Bengaluru 560088", "primary_contact": "+91-80-2846-5678", "authorized_signatory": "Savitha Gowda", "employee_headcount": 42, "operational_status": "active", "license_status": "valid", "safety_clearance": "approved", "last_inspection_date": "2026-02-08"},
]


def _build_sws_batch() -> list[dict]:
    """All 20 businesses in SWS format."""
    return [
        {
            "ubid": b["ubid"],
            "business_name": b["business_name"],
            "registered_address": b["registered_address"],
            "primary_contact": b["primary_contact"],
            "authorized_signatory": b["authorized_signatory"],
            "employee_headcount": b["employee_headcount"],
            "operational_status": b["operational_status"],
            "license_status": b["license_status"],
            "safety_clearance": b["safety_clearance"],
            "last_inspection_date": b["last_inspection_date"],
        }
        for b in _SEED_BUSINESSES
    ]


def _build_shop_batch() -> list[dict]:
    """First 18 businesses in Shop Establishment format."""
    return [
        {
            "shop_reg_no": f"SHOP-{i + 1:04d}",
            "ubid": b["ubid"],
            "business_name": b["business_name"],
            "Buss_Addr_Line1": b["registered_address"],
            "Contact_Phone": b["primary_contact"],
            "Auth_Sign_Name": b["authorized_signatory"],
            "Emp_Count": b["employee_headcount"],
            "Op_Status": b["operational_status"],
            "Lic_Status": b["license_status"],
        }
        for i, b in enumerate(_SEED_BUSINESSES[:18])
    ]


def _build_factories_batch() -> list[dict]:
    """First 15 businesses in Factories format."""
    return [
        {
            "factory_license_no": f"FACT-{i + 1:04d}",
            "ubid": b["ubid"],
            "business_name": b["business_name"],
            "factory_address": b["registered_address"],
            "contact_number": b["primary_contact"],
            "signatory_name": b["authorized_signatory"],
            "worker_count": b["employee_headcount"],
            "factory_status": b["operational_status"],
            "lic_status": b["license_status"],
            "safety_cert": b["safety_clearance"],
            "labor_violations": "none",
            "last_inspection_date": b["last_inspection_date"],
        }
        for i, b in enumerate(_SEED_BUSINESSES[:15])
    ]


# ── System config ──────────────────────────────────────────────────────────────

# Map system name → base URL and endpoint patterns
_SYSTEM_CONFIG = {
    "sws": {
        "base_url": settings.mock_systems.sws_base_url,
        "list_path": "/api/businesses",
        "get_path": "/api/businesses/{ubid}",
        "put_path": "/api/businesses/{ubid}",
        "batch_path": "/api/businesses/batch",
        "clear_path": "/api/businesses/all",
    },
    "shop": {
        "base_url": settings.mock_systems.shop_base_url,
        "list_path": "/api/records",
        "get_path": "/api/records/by-ubid/{ubid}",
        "put_path": "/api/records/by-ubid/{ubid}",
        "batch_path": "/api/records/batch",
        "clear_path": "/api/records/all",
    },
    "factories": {
        "base_url": settings.mock_systems.factories_base_url,
        "list_path": "/api/records",
        "get_path": "/api/records/by-ubid/{ubid}",
        "put_path": "/api/records/by-ubid/{ubid}",
        "batch_path": "/api/records/batch",
        "clear_path": "/api/records/all",
    },
}


def _get_config(system: str) -> dict:
    if system not in _SYSTEM_CONFIG:
        raise HTTPException(status_code=400, detail=f"Unknown system: {system}. Use sws, shop, or factories.")
    return _SYSTEM_CONFIG[system]


# ── Existing proxy routes (unchanged) ─────────────────────────────────────────

@router.get("/mock/{system}/businesses")
async def list_records(system: str):
    """List all records from a mock system."""
    cfg = _get_config(system)
    url = cfg["base_url"] + cfg["list_path"]
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        logger.error("mock_proxy_error", system=system, url=url, error=str(e))
        raise HTTPException(status_code=502, detail=f"Mock system unreachable: {e}")


@router.get("/mock/{system}/record/{ubid}")
async def get_record(system: str, ubid: str):
    """Get a single record by UBID from a mock system."""
    cfg = _get_config(system)
    path = cfg["get_path"].format(ubid=ubid)
    url = cfg["base_url"] + path
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(url)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        logger.error("mock_proxy_error", system=system, ubid=ubid, url=url, error=str(e))
        raise HTTPException(status_code=502, detail=f"Mock system unreachable: {e}")


@router.put("/mock/{system}/record/{ubid}")
async def update_record(system: str, ubid: str, request: Request):
    """Update a record by UBID in a mock system."""
    cfg = _get_config(system)
    path = cfg["put_path"].format(ubid=ubid)
    url = cfg["base_url"] + path
    body = await request.json()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.put(url, json=body)
            return JSONResponse(content=resp.json(), status_code=resp.status_code)
    except Exception as e:
        logger.error("mock_proxy_error", system=system, ubid=ubid, url=url, error=str(e))
        raise HTTPException(status_code=502, detail=f"Mock system unreachable: {e}")


# ── Seed / Reset endpoints ─────────────────────────────────────────────────────

async def _do_seed(client: httpx.AsyncClient) -> dict:
    """Call batch-create on all three systems. Returns counts seeded."""
    sws_cfg = _SYSTEM_CONFIG["sws"]
    shop_cfg = _SYSTEM_CONFIG["shop"]
    fact_cfg = _SYSTEM_CONFIG["factories"]

    sws_resp = await client.post(sws_cfg["base_url"] + sws_cfg["batch_path"], json=_build_sws_batch())
    shop_resp = await client.post(shop_cfg["base_url"] + shop_cfg["batch_path"], json=_build_shop_batch())
    fact_resp = await client.post(fact_cfg["base_url"] + fact_cfg["batch_path"], json=_build_factories_batch())

    return {
        "sws": sws_resp.json().get("created", 0) if sws_resp.is_success else 0,
        "shop": shop_resp.json().get("created", 0) if shop_resp.is_success else 0,
        "factories": fact_resp.json().get("created", 0) if fact_resp.is_success else 0,
    }


@router.post("/mock/seed")
async def seed_all():
    """
    Seed all three mock systems with the full 20-business dataset.
    Uses INSERT OR REPLACE — safe to call on already-seeded systems.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            counts = await _do_seed(client)
        logger.info("mock_seed_complete", counts=counts)
        return {"seeded": counts, "total": sum(counts.values())}
    except Exception as e:
        logger.error("mock_seed_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Seed failed: {e}")


@router.post("/mock/reset")
async def reset_all():
    """
    Clear all records from all three mock systems, then reseed with the full dataset.
    Useful for resetting demo state to a clean baseline.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            # Step 1: clear all three systems
            sws_cfg = _SYSTEM_CONFIG["sws"]
            shop_cfg = _SYSTEM_CONFIG["shop"]
            fact_cfg = _SYSTEM_CONFIG["factories"]

            await client.delete(sws_cfg["base_url"] + sws_cfg["clear_path"])
            await client.delete(shop_cfg["base_url"] + shop_cfg["clear_path"])
            await client.delete(fact_cfg["base_url"] + fact_cfg["clear_path"])

            # Step 2: reseed
            counts = await _do_seed(client)

        logger.info("mock_reset_complete", counts=counts)
        return {"cleared": True, "seeded": counts, "total": sum(counts.values())}
    except Exception as e:
        logger.error("mock_reset_error", error=str(e))
        raise HTTPException(status_code=502, detail=f"Reset failed: {e}")

@router.post("/mock/hard_reset")
async def hard_reset_all():
    """
    Clears all records from mock systems AND truncates the SyncKar PostgreSQL DB + Redis.
    Provides a completely clean slate for demo purposes.
    """
    # 1. Reset mock systems
    mock_reset_result = await reset_all()
    
    # 2. Reset Postgres DB
    try:
        from synckar.db import get_conn, put_conn
        conn = get_conn()
        cursor = conn.cursor()
        cursor.execute("TRUNCATE audit_ledger, conflict_log, dead_letter_queue, outbox, poller_state, dept_snapshots CASCADE;")
        conn.commit()
        put_conn(conn)
        db_cleared = True
    except Exception as e:
        logger.error("db_truncate_failed", error=str(e))
        db_cleared = False
        
    # 3. Reset Redis
    try:
        import redis
        r = redis.Redis.from_url(settings.redis.url, decode_responses=True)
        deleted = 0
        for pattern in ["sws:watermark", "factories:watermark", "shop_establishment:watermark", "idem:*", "conflict_window:*", "circuit:*", "rate_limit:*"]:
            keys = r.keys(pattern)
            if keys:
                deleted += r.delete(*keys)
        redis_cleared = True
    except Exception as e:
        logger.error("redis_flush_failed", error=str(e))
        redis_cleared = False
        
    return {
        "mock_systems": mock_reset_result,
        "database_truncated": db_cleared,
        "redis_cleared": redis_cleared
    }

@router.post("/mock/scenario/{name}")
async def run_scenario(name: str):
    """
    Executes a predefined demo scenario (a, b, c) from the UI.
    Uses httpx to interact with the mock system API exactly as the python scripts do.
    """
    import time
    ubid = "KA-TEST-0001"
    
    sws_cfg = _SYSTEM_CONFIG["sws"]
    shop_cfg = _SYSTEM_CONFIG["shop"]
    fact_cfg = _SYSTEM_CONFIG["factories"]
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if name == "a":
                # Scenario A: SWS Address Update -> Propagation
                new_addr = f"999 New MG Road, Indiranagar, Bangalore 560038 ({int(time.time())})"
                await client.put(sws_cfg["base_url"] + sws_cfg["put_path"].format(ubid=ubid), json={"registered_address": new_addr})
                return {"scenario": "a", "action": "updated SWS address", "ubid": ubid, "new_value": new_addr}
                
            elif name == "b":
                # Scenario B: Factories Signatory Update -> Reverse Propagation
                new_sig = f"Rajesh Kumar Sharma (Updated {int(time.time() % 10000)})"
                await client.put(fact_cfg["base_url"] + fact_cfg["put_path"].format(ubid=ubid), json={"signatory_name": new_sig})
                return {"scenario": "b", "action": "updated Factories signatory", "ubid": ubid, "new_value": new_sig}
                
            elif name == "c":
                # Scenario C: Simultaneous Conflict
                conflict_val_a = f"SWS Conflict Addr {int(time.time())}"
                conflict_val_b = f"Factories Conflict Addr {int(time.time())}"
                
                # Fire almost simultaneously
                import asyncio
                await asyncio.gather(
                    client.put(sws_cfg["base_url"] + sws_cfg["put_path"].format(ubid=ubid), json={"registered_address": conflict_val_a}),
                    client.put(fact_cfg["base_url"] + fact_cfg["put_path"].format(ubid=ubid), json={"factory_address": conflict_val_b})
                )
                return {"scenario": "c", "action": "triggered conflict", "ubid": ubid, "sws_value": conflict_val_a, "factories_value": conflict_val_b}
                
            else:
                raise HTTPException(status_code=400, detail="Unknown scenario")
                
    except Exception as e:
        logger.error("scenario_run_error", scenario=name, error=str(e))
        raise HTTPException(status_code=502, detail=f"Scenario failed: {e}")


@router.post("/mock/seed_dlq")
async def seed_dlq():
    """
    Insert realistic mock DLQ entries for demo purposes.
    These simulate real failure scenarios that the Data Steward dashboard handles.
    """
    import uuid
    from synckar.db import get_conn, put_conn
    from datetime import datetime, timedelta

    dlq_entries = [
        {
            "correlation_id": str(uuid.uuid4()),
            "ubid": "KA-TEST-0007",
            "raw_payload": json.dumps({
                "ubid": "KA-TEST-0007",
                "source_system": "dept_shop_establishment",
                "field_name": "registered_address",
                "new_value": "KIADB Phase II, Tumakuru 572106 (Updated)",
                "correlation_id": str(uuid.uuid4()),
            }),
            "error_reason": "SOAP endpoint unreachable: ConnectionTimeout after 30s — Shop Establishment API at shop-est.karnataka.gov.in:8443 refused connection. Retry exhausted after 10 attempts with exponential backoff (max 30min).",
            "source_system": "dept_shop_establishment",
        },
        {
            "correlation_id": str(uuid.uuid4()),
            "ubid": "KA-TEST-0012",
            "raw_payload": json.dumps({
                "ubid": "KA-TEST-0012",
                "source_system": "sws",
                "field_name": "license_status",
                "new_value": "renewed",
                "correlation_id": str(uuid.uuid4()),
            }),
            "error_reason": "Schema drift detected: field 'Lic_Status' expected enum ['valid','expired','suspended','revoked'] but received 'renewed'. Record quarantined — mapping_v3.yaml does not cover this value. Requires Data Steward review.",
            "source_system": "sws",
        },
        {
            "correlation_id": str(uuid.uuid4()),
            "ubid": "KA-TEST-0015",
            "raw_payload": json.dumps({
                "ubid": "KA-TEST-0015",
                "source_system": "dept_factories",
                "field_name": "worker_count",
                "new_value": "780",
                "correlation_id": str(uuid.uuid4()),
            }),
            "error_reason": "PermanentWriteError: Factories API returned HTTP 422 — 'worker_count exceeds registered factory capacity of 500'. Business rule violation at target. Cannot auto-resolve.",
            "source_system": "dept_factories",
        },
    ]

    try:
        conn = get_conn()
        cursor = conn.cursor()
        for entry in dlq_entries:
            cursor.execute(
                """
                INSERT INTO dead_letter_queue (correlation_id, ubid, raw_payload, error_reason, source_system, status)
                VALUES (%s::uuid, %s, %s, %s, %s, 'PENDING')
                """,
                (
                    entry["correlation_id"],
                    entry["ubid"],
                    entry["raw_payload"],
                    entry["error_reason"],
                    entry["source_system"],
                ),
            )
        conn.commit()
        put_conn(conn)
        return {"seeded": len(dlq_entries), "message": "DLQ demo entries created"}
    except Exception as e:
        logger.error("seed_dlq_error", error=str(e))
        raise HTTPException(status_code=500, detail=f"DLQ seed failed: {e}")
