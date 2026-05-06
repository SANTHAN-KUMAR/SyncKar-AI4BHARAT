"""
Mock SWS (Single Window System) — FastAPI application with SQLite persistence.
Data survives container restarts. Auto-seeds on first startup.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Mock SWS — Karnataka Single Window System", version="1.0.0")

DB_PATH = os.environ.get("SWS_DB_PATH", "/tmp/mock_sws.db")

# ── Seed data — all 20 Karnataka businesses ────────────────────────────────
SEED_BUSINESSES = [
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


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS businesses (
                ubid TEXT PRIMARY KEY,
                data TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS changes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ubid TEXT NOT NULL,
                data TEXT NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        conn.commit()


@contextmanager
def db_conn():
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def auto_seed():
    """Seed the database on first startup if it is empty. Skips if records exist."""
    with db_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
        if count > 0:
            return  # DB already has data — do not overwrite
        now = datetime.now(timezone.utc).isoformat()
        for biz in SEED_BUSINESSES:
            data = {**biz, "last_modified": now, "modified_by": "auto_seed"}
            conn.execute(
                "INSERT OR REPLACE INTO businesses (ubid, data) VALUES (?, ?)",
                (biz["ubid"], json.dumps(data))
            )
    print(f"[mock_sws] auto_seed: inserted {len(SEED_BUSINESSES)} businesses", flush=True)


init_db()
auto_seed()


class BusinessRecord(BaseModel):
    ubid: str
    business_name: str
    registered_address: str = ""
    primary_contact: str = ""
    authorized_signatory: str = ""
    employee_headcount: int = 0
    operational_status: str = "active"
    license_status: str = "valid"
    safety_clearance: str = "approved"
    last_inspection_date: str = ""
    last_modified: str = ""
    modified_by: str = "system"


class BusinessUpdate(BaseModel):
    registered_address: Optional[str] = None
    primary_contact: Optional[str] = None
    authorized_signatory: Optional[str] = None
    employee_headcount: Optional[int] = None
    operational_status: Optional[str] = None
    license_status: Optional[str] = None
    safety_clearance: Optional[str] = None
    last_inspection_date: Optional[str] = None
    modified_by: Optional[str] = "sws_user"


@app.get("/health")
def health():
    with db_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM businesses").fetchone()[0]
    return {"status": "healthy", "system": "mock_sws", "businesses": count}


@app.get("/api/businesses")
def list_businesses():
    with db_conn() as conn:
        rows = conn.execute("SELECT data FROM businesses").fetchall()
    businesses = [json.loads(r["data"]) for r in rows]
    return {"businesses": businesses, "count": len(businesses)}


@app.get("/api/businesses/changes")
def get_changes(since: str = Query(default="2000-01-01T00:00:00Z")):
    try:
        since_dt = datetime.fromisoformat(since.replace("Z", "+00:00"))
    except ValueError:
        since_dt = datetime.min.replace(tzinfo=timezone.utc)

    with db_conn() as conn:
        rows = conn.execute(
            "SELECT data FROM changes WHERE timestamp > ? ORDER BY id",
            (since_dt.isoformat(),)
        ).fetchall()
    result = [json.loads(r["data"]) for r in rows]
    return {"changes": result, "count": len(result), "since": since}


@app.get("/api/businesses/{ubid}")
def get_business(ubid: str):
    with db_conn() as conn:
        row = conn.execute("SELECT data FROM businesses WHERE ubid = ?", (ubid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"UBID {ubid} not found in SWS")
    return json.loads(row["data"])


@app.put("/api/businesses/{ubid}")
def update_business(ubid: str, update: BusinessUpdate):
    with db_conn() as conn:
        row = conn.execute("SELECT data FROM businesses WHERE ubid = ?", (ubid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"UBID {ubid} not found in SWS")

        business = json.loads(row["data"])
        now = datetime.now(timezone.utc).isoformat()
        updated_fields = []

        update_data = update.model_dump(exclude_none=True)
        for field, new_value in update_data.items():
            if field == "modified_by":
                continue
            old_value = business.get(field)
            if str(old_value) != str(new_value):
                change = {
                    "ubid": ubid,
                    "field_name": field,
                    "old_value": str(old_value) if old_value is not None else None,
                    "new_value": str(new_value),
                    "timestamp": now,
                    "source": "sws",
                    "event_id": f"sws-{ubid}-{field}-{now}",
                }
                conn.execute(
                    "INSERT INTO changes (ubid, data, timestamp) VALUES (?, ?, ?)",
                    (ubid, json.dumps(change), now)
                )
                business[field] = new_value
                updated_fields.append(field)

        business["last_modified"] = now
        business["modified_by"] = update_data.get("modified_by", "sws_user")
        conn.execute("UPDATE businesses SET data = ? WHERE ubid = ?", (json.dumps(business), ubid))

    return {"ubid": ubid, "updated_fields": updated_fields, "timestamp": now, "business": business}


@app.post("/api/businesses")
def create_business(business: BusinessRecord):
    now = datetime.now(timezone.utc).isoformat()
    data = business.model_dump()
    data["last_modified"] = now
    with db_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO businesses (ubid, data) VALUES (?, ?)",
            (business.ubid, json.dumps(data))
        )
    return {"ubid": business.ubid, "created": True}


@app.post("/api/businesses/batch")
def batch_create(businesses: list[BusinessRecord]):
    now = datetime.now(timezone.utc).isoformat()
    with db_conn() as conn:
        for biz in businesses:
            data = biz.model_dump()
            data["last_modified"] = now
            conn.execute(
                "INSERT OR REPLACE INTO businesses (ubid, data) VALUES (?, ?)",
                (biz.ubid, json.dumps(data))
            )
    return {"created": len(businesses)}


@app.delete("/api/businesses/all")
def clear_all():
    """Clear all data (for reset)."""
    with db_conn() as conn:
        conn.execute("DELETE FROM businesses")
        conn.execute("DELETE FROM changes")
    return {"cleared": True}
