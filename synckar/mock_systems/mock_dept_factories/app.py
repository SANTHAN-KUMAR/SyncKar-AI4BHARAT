"""
Mock Factories Department — FastAPI with SQLite persistence.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Mock Factories Department", version="1.0.0")

DB_PATH = os.environ.get("FACTORIES_DB_PATH", "/tmp/mock_factories.db")

# ── Seed data — 15 Factories records (KA-TEST-0001 to KA-TEST-0015) ──────────
SEED_FACTORY_RECORDS = [
    {"factory_license_no": "FACT-0001", "ubid": "KA-TEST-0001", "business_name": "Bengaluru Silk Weavers Pvt Ltd", "factory_address": "14 Cunningham Road, Bengaluru 560052", "contact_number": "+91-80-4112-3456", "signatory_name": "Rajesh Kumar Sharma", "worker_count": 85, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-01-15"},
    {"factory_license_no": "FACT-0002", "ubid": "KA-TEST-0002", "business_name": "Mysuru Agro Industries Ltd", "factory_address": "Plot 22, KIADB Industrial Area, Mysuru 570016", "contact_number": "+91-821-2412-789", "signatory_name": "Priya Venkatesh", "worker_count": 142, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-02-10"},
    {"factory_license_no": "FACT-0003", "ubid": "KA-TEST-0003", "business_name": "Hubli Steel Fabricators Pvt Ltd", "factory_address": "Survey No. 45, Gokul Road, Hubballi 580030", "contact_number": "+91-836-2234-567", "signatory_name": "Suresh Basavaraj", "worker_count": 210, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-01-28"},
    {"factory_license_no": "FACT-0004", "ubid": "KA-TEST-0004", "business_name": "Mangaluru Cashew Exports Ltd", "factory_address": "Bunder Road, Mangaluru 575001", "contact_number": "+91-824-2441-234", "signatory_name": "Anitha D'Souza", "worker_count": 67, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-03-05"},
    {"factory_license_no": "FACT-0005", "ubid": "KA-TEST-0005", "business_name": "Dharwad Pharma Solutions Pvt Ltd", "factory_address": "KSSIDC Industrial Estate, Dharwad 580004", "contact_number": "+91-836-2448-901", "signatory_name": "Dr. Kavitha Patil", "worker_count": 320, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-02-20"},
    {"factory_license_no": "FACT-0006", "ubid": "KA-TEST-0006", "business_name": "Belagavi Textile Mills Ltd", "factory_address": "Udyambag Industrial Area, Belagavi 590008", "contact_number": "+91-831-2423-678", "signatory_name": "Mahesh Kulkarni", "worker_count": 450, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-01-10"},
    {"factory_license_no": "FACT-0007", "ubid": "KA-TEST-0007", "business_name": "Tumkur Auto Components Pvt Ltd", "factory_address": "KIADB Phase II, Tumakuru 572106", "contact_number": "+91-816-2272-345", "signatory_name": "Ravi Shankar Gowda", "worker_count": 178, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-03-12"},
    {"factory_license_no": "FACT-0008", "ubid": "KA-TEST-0008", "business_name": "Shivamogga Paper Industries Ltd", "factory_address": "Bhadravathi Road, Shivamogga 577201", "contact_number": "+91-8182-223456", "signatory_name": "Lakshmi Narayana", "worker_count": 290, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-02-05"},
    {"factory_license_no": "FACT-0009", "ubid": "KA-TEST-0009", "business_name": "Kolar Gold Jewellers Pvt Ltd", "factory_address": "B B Road, Kolar 563101", "contact_number": "+91-8152-222789", "signatory_name": "Srinivas Reddy", "worker_count": 45, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-01-22"},
    {"factory_license_no": "FACT-0010", "ubid": "KA-TEST-0010", "business_name": "Raichur Power Equipment Ltd", "factory_address": "Industrial Area, Raichur 584101", "contact_number": "+91-8532-226789", "signatory_name": "Abdul Kareem", "worker_count": 520, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-03-01"},
    {"factory_license_no": "FACT-0011", "ubid": "KA-TEST-0011", "business_name": "Bidar Ceramics Pvt Ltd", "factory_address": "Udgir Road, Bidar 585401", "contact_number": "+91-8482-227890", "signatory_name": "Fatima Begum", "worker_count": 95, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-02-15"},
    {"factory_license_no": "FACT-0012", "ubid": "KA-TEST-0012", "business_name": "Vijayapura Sugar Mills Ltd", "factory_address": "Solapur Road, Vijayapura 586101", "contact_number": "+91-8352-250123", "signatory_name": "Basavaraj Patil", "worker_count": 680, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-01-05"},
    {"factory_license_no": "FACT-0013", "ubid": "KA-TEST-0013", "business_name": "Gadag Granite Exports Pvt Ltd", "factory_address": "NH-67, Gadag 582101", "contact_number": "+91-8372-234567", "signatory_name": "Veeranna Hiremath", "worker_count": 130, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-03-18"},
    {"factory_license_no": "FACT-0014", "ubid": "KA-TEST-0014", "business_name": "Koppal Iron & Steel Ltd", "factory_address": "Gangavathi Road, Koppal 583231", "contact_number": "+91-8539-220456", "signatory_name": "Nagaraj Bellad", "worker_count": 410, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-02-28"},
    {"factory_license_no": "FACT-0015", "ubid": "KA-TEST-0015", "business_name": "Yadgir Cement Works Pvt Ltd", "factory_address": "Gulbarga Road, Yadgir 585201", "contact_number": "+91-8473-221789", "signatory_name": "Chandrashekhar Rao", "worker_count": 750, "factory_status": "active", "lic_status": "valid", "safety_cert": "approved", "labor_violations": "none", "last_inspection_date": "2026-01-30"},
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                factory_license_no TEXT PRIMARY KEY,
                ubid TEXT NOT NULL,
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
        count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
        if count > 0:
            return  # DB already has data — do not overwrite
        now = datetime.now(timezone.utc).isoformat()
        for rec in SEED_FACTORY_RECORDS:
            data = {**rec, "last_modified": now}
            conn.execute(
                "INSERT OR REPLACE INTO records (factory_license_no, ubid, data) VALUES (?, ?, ?)",
                (rec["factory_license_no"], rec["ubid"], json.dumps(data))
            )
    print(f"[mock_factories] auto_seed: inserted {len(SEED_FACTORY_RECORDS)} records", flush=True)


init_db()
auto_seed()


class FactoryRecord(BaseModel):
    factory_license_no: str
    ubid: str
    business_name: str
    factory_address: str = ""
    contact_number: str = ""
    signatory_name: str = ""
    worker_count: int = 0
    factory_status: str = "active"
    lic_status: str = "valid"
    safety_cert: str = "approved"
    labor_violations: str = "none"
    last_inspection_date: str = ""
    last_modified: str = ""


class FactoryUpdate(BaseModel):
    factory_address: Optional[str] = None
    contact_number: Optional[str] = None
    signatory_name: Optional[str] = None
    worker_count: Optional[int] = None
    factory_status: Optional[str] = None
    lic_status: Optional[str] = None
    safety_cert: Optional[str] = None
    labor_violations: Optional[str] = None
    last_inspection_date: Optional[str] = None


@app.get("/health")
def health():
    with db_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    return {"status": "healthy", "system": "mock_factories", "records": count}


@app.get("/api/records")
def list_records():
    with db_conn() as conn:
        rows = conn.execute("SELECT data FROM records").fetchall()
    records = [json.loads(r["data"]) for r in rows]
    return {"records": records, "count": len(records)}


@app.get("/api/records/changes")
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


@app.get("/api/records/by-ubid/{ubid}")
def get_by_ubid(ubid: str):
    with db_conn() as conn:
        row = conn.execute("SELECT data FROM records WHERE ubid = ?", (ubid,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"UBID {ubid} not found in Factories")
    return json.loads(row["data"])


@app.put("/api/records/by-ubid/{ubid}")
def update_by_ubid(ubid: str, update: FactoryUpdate):
    with db_conn() as conn:
        row = conn.execute("SELECT data, factory_license_no FROM records WHERE ubid = ?", (ubid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"UBID {ubid} not found in Factories")

        record = json.loads(row["data"])
        license_no = row["factory_license_no"]
        now = datetime.now(timezone.utc).isoformat()
        updated_fields = []

        update_data = update.model_dump(exclude_none=True)
        for field, new_value in update_data.items():
            old_value = record.get(field)
            if str(old_value) != str(new_value):
                change = {
                    "ubid": ubid,
                    "factory_license_no": license_no,
                    "field_name": field,
                    "old_value": str(old_value) if old_value is not None else None,
                    "new_value": str(new_value),
                    "timestamp": now,
                    "source": "factories",
                    "event_id": f"fact-{ubid}-{field}-{now}",
                }
                conn.execute(
                    "INSERT INTO changes (ubid, data, timestamp) VALUES (?, ?, ?)",
                    (ubid, json.dumps(change), now)
                )
                record[field] = new_value
                updated_fields.append(field)

        record["last_modified"] = now
        conn.execute("UPDATE records SET data = ? WHERE ubid = ?", (json.dumps(record), ubid))

    return {"ubid": ubid, "updated_fields": updated_fields, "record": record}


@app.post("/api/records")
def create_record(record: FactoryRecord):
    now = datetime.now(timezone.utc).isoformat()
    data = record.model_dump()
    data["last_modified"] = now
    with db_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO records (factory_license_no, ubid, data) VALUES (?, ?, ?)",
            (record.factory_license_no, record.ubid, json.dumps(data))
        )
    return {"factory_license_no": record.factory_license_no, "created": True}


@app.post("/api/records/batch")
def batch_create(records: list[FactoryRecord]):
    now = datetime.now(timezone.utc).isoformat()
    with db_conn() as conn:
        for rec in records:
            data = rec.model_dump()
            data["last_modified"] = now
            conn.execute(
                "INSERT OR REPLACE INTO records (factory_license_no, ubid, data) VALUES (?, ?, ?)",
                (rec.factory_license_no, rec.ubid, json.dumps(data))
            )
    return {"created": len(records)}


@app.delete("/api/records/all")
def clear_all():
    with db_conn() as conn:
        conn.execute("DELETE FROM records")
        conn.execute("DELETE FROM changes")
    return {"cleared": True}
