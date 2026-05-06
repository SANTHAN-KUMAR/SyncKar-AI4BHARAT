"""
Mock Shop Establishment Department — FastAPI with SQLite persistence.
"""

import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

app = FastAPI(title="Mock Shop Establishment Department", version="1.0.0")

DB_PATH = os.environ.get("SHOP_DB_PATH", "/tmp/mock_shop.db")

# ── Seed data — 18 Shop Establishment records (KA-TEST-0001 to KA-TEST-0018) ─
SEED_SHOP_RECORDS = [
    {"shop_reg_no": "SHOP-0001", "ubid": "KA-TEST-0001", "business_name": "Bengaluru Silk Weavers Pvt Ltd", "Buss_Addr_Line1": "14 Cunningham Road, Bengaluru 560052", "Contact_Phone": "+91-80-4112-3456", "Auth_Sign_Name": "Rajesh Kumar Sharma", "Emp_Count": 85, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0002", "ubid": "KA-TEST-0002", "business_name": "Mysuru Agro Industries Ltd", "Buss_Addr_Line1": "Plot 22, KIADB Industrial Area, Mysuru 570016", "Contact_Phone": "+91-821-2412-789", "Auth_Sign_Name": "Priya Venkatesh", "Emp_Count": 142, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0003", "ubid": "KA-TEST-0003", "business_name": "Hubli Steel Fabricators Pvt Ltd", "Buss_Addr_Line1": "Survey No. 45, Gokul Road, Hubballi 580030", "Contact_Phone": "+91-836-2234-567", "Auth_Sign_Name": "Suresh Basavaraj", "Emp_Count": 210, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0004", "ubid": "KA-TEST-0004", "business_name": "Mangaluru Cashew Exports Ltd", "Buss_Addr_Line1": "Bunder Road, Mangaluru 575001", "Contact_Phone": "+91-824-2441-234", "Auth_Sign_Name": "Anitha D'Souza", "Emp_Count": 67, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0005", "ubid": "KA-TEST-0005", "business_name": "Dharwad Pharma Solutions Pvt Ltd", "Buss_Addr_Line1": "KSSIDC Industrial Estate, Dharwad 580004", "Contact_Phone": "+91-836-2448-901", "Auth_Sign_Name": "Dr. Kavitha Patil", "Emp_Count": 320, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0006", "ubid": "KA-TEST-0006", "business_name": "Belagavi Textile Mills Ltd", "Buss_Addr_Line1": "Udyambag Industrial Area, Belagavi 590008", "Contact_Phone": "+91-831-2423-678", "Auth_Sign_Name": "Mahesh Kulkarni", "Emp_Count": 450, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0007", "ubid": "KA-TEST-0007", "business_name": "Tumkur Auto Components Pvt Ltd", "Buss_Addr_Line1": "KIADB Phase II, Tumakuru 572106", "Contact_Phone": "+91-816-2272-345", "Auth_Sign_Name": "Ravi Shankar Gowda", "Emp_Count": 178, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0008", "ubid": "KA-TEST-0008", "business_name": "Shivamogga Paper Industries Ltd", "Buss_Addr_Line1": "Bhadravathi Road, Shivamogga 577201", "Contact_Phone": "+91-8182-223456", "Auth_Sign_Name": "Lakshmi Narayana", "Emp_Count": 290, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0009", "ubid": "KA-TEST-0009", "business_name": "Kolar Gold Jewellers Pvt Ltd", "Buss_Addr_Line1": "B B Road, Kolar 563101", "Contact_Phone": "+91-8152-222789", "Auth_Sign_Name": "Srinivas Reddy", "Emp_Count": 45, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0010", "ubid": "KA-TEST-0010", "business_name": "Raichur Power Equipment Ltd", "Buss_Addr_Line1": "Industrial Area, Raichur 584101", "Contact_Phone": "+91-8532-226789", "Auth_Sign_Name": "Abdul Kareem", "Emp_Count": 520, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0011", "ubid": "KA-TEST-0011", "business_name": "Bidar Ceramics Pvt Ltd", "Buss_Addr_Line1": "Udgir Road, Bidar 585401", "Contact_Phone": "+91-8482-227890", "Auth_Sign_Name": "Fatima Begum", "Emp_Count": 95, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0012", "ubid": "KA-TEST-0012", "business_name": "Vijayapura Sugar Mills Ltd", "Buss_Addr_Line1": "Solapur Road, Vijayapura 586101", "Contact_Phone": "+91-8352-250123", "Auth_Sign_Name": "Basavaraj Patil", "Emp_Count": 680, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0013", "ubid": "KA-TEST-0013", "business_name": "Gadag Granite Exports Pvt Ltd", "Buss_Addr_Line1": "NH-67, Gadag 582101", "Contact_Phone": "+91-8372-234567", "Auth_Sign_Name": "Veeranna Hiremath", "Emp_Count": 130, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0014", "ubid": "KA-TEST-0014", "business_name": "Koppal Iron & Steel Ltd", "Buss_Addr_Line1": "Gangavathi Road, Koppal 583231", "Contact_Phone": "+91-8539-220456", "Auth_Sign_Name": "Nagaraj Bellad", "Emp_Count": 410, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0015", "ubid": "KA-TEST-0015", "business_name": "Yadgir Cement Works Pvt Ltd", "Buss_Addr_Line1": "Gulbarga Road, Yadgir 585201", "Contact_Phone": "+91-8473-221789", "Auth_Sign_Name": "Chandrashekhar Rao", "Emp_Count": 750, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0016", "ubid": "KA-TEST-0016", "business_name": "Bengaluru IT Solutions Pvt Ltd", "Buss_Addr_Line1": "Whitefield, Bengaluru 560066", "Contact_Phone": "+91-80-4567-8901", "Auth_Sign_Name": "Deepa Krishnamurthy", "Emp_Count": 230, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0017", "ubid": "KA-TEST-0017", "business_name": "Mysuru Handicrafts Emporium", "Buss_Addr_Line1": "Sayyaji Rao Road, Mysuru 570001", "Contact_Phone": "+91-821-2423-456", "Auth_Sign_Name": "Geetha Nagaraj", "Emp_Count": 38, "Op_Status": "active", "Lic_Status": "valid"},
    {"shop_reg_no": "SHOP-0018", "ubid": "KA-TEST-0018", "business_name": "Mangaluru Seafood Processors Ltd", "Buss_Addr_Line1": "Panambur, Mangaluru 575010", "Contact_Phone": "+91-824-2456-789", "Auth_Sign_Name": "Peter Fernandes", "Emp_Count": 165, "Op_Status": "active", "Lic_Status": "valid"},
]


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS records (
                shop_reg_no TEXT PRIMARY KEY,
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
        for rec in SEED_SHOP_RECORDS:
            data = {**rec, "last_modified": now}
            conn.execute(
                "INSERT OR REPLACE INTO records (shop_reg_no, ubid, data) VALUES (?, ?, ?)",
                (rec["shop_reg_no"], rec["ubid"], json.dumps(data))
            )
    print(f"[mock_shop] auto_seed: inserted {len(SEED_SHOP_RECORDS)} records", flush=True)


init_db()
auto_seed()


class ShopRecord(BaseModel):
    shop_reg_no: str
    ubid: str
    business_name: str
    Buss_Addr_Line1: str = ""
    Contact_Phone: str = ""
    Auth_Sign_Name: str = ""
    Emp_Count: int = 0
    Op_Status: str = "active"
    Lic_Status: str = "valid"
    last_modified: str = ""


class ShopUpdate(BaseModel):
    Buss_Addr_Line1: Optional[str] = None
    Contact_Phone: Optional[str] = None
    Auth_Sign_Name: Optional[str] = None
    Emp_Count: Optional[int] = None
    Op_Status: Optional[str] = None
    Lic_Status: Optional[str] = None


@app.get("/health")
def health():
    with db_conn() as conn:
        count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
    return {"status": "healthy", "system": "mock_shop_establishment", "records": count}


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
        raise HTTPException(status_code=404, detail=f"UBID {ubid} not found in Shop Establishment")
    return json.loads(row["data"])


@app.put("/api/records/by-ubid/{ubid}")
def update_by_ubid(ubid: str, update: ShopUpdate):
    with db_conn() as conn:
        row = conn.execute("SELECT data, shop_reg_no FROM records WHERE ubid = ?", (ubid,)).fetchone()
        if not row:
            raise HTTPException(status_code=404, detail=f"UBID {ubid} not found in Shop Establishment")

        record = json.loads(row["data"])
        shop_reg = row["shop_reg_no"]
        now = datetime.now(timezone.utc).isoformat()
        updated_fields = []

        update_data = update.model_dump(exclude_none=True)
        for field, new_value in update_data.items():
            old_value = record.get(field)
            if str(old_value) != str(new_value):
                change = {
                    "ubid": ubid,
                    "shop_reg_no": shop_reg,
                    "field_name": field,
                    "old_value": str(old_value) if old_value is not None else None,
                    "new_value": str(new_value),
                    "timestamp": now,
                    "source": "shop_establishment",
                    "event_id": f"shop-{ubid}-{field}-{now}",
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
def create_record(record: ShopRecord):
    now = datetime.now(timezone.utc).isoformat()
    data = record.model_dump()
    data["last_modified"] = now
    with db_conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO records (shop_reg_no, ubid, data) VALUES (?, ?, ?)",
            (record.shop_reg_no, record.ubid, json.dumps(data))
        )
    return {"shop_reg_no": record.shop_reg_no, "created": True}


@app.post("/api/records/batch")
def batch_create(records: list[ShopRecord]):
    now = datetime.now(timezone.utc).isoformat()
    with db_conn() as conn:
        for rec in records:
            data = rec.model_dump()
            data["last_modified"] = now
            conn.execute(
                "INSERT OR REPLACE INTO records (shop_reg_no, ubid, data) VALUES (?, ?, ?)",
                (rec.shop_reg_no, rec.ubid, json.dumps(data))
            )
    return {"created": len(records)}


@app.delete("/api/records/all")
def clear_all():
    with db_conn() as conn:
        conn.execute("DELETE FROM records")
        conn.execute("DELETE FROM changes")
    return {"cleared": True}
