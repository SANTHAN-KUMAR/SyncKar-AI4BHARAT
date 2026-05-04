"""
Reconciliation job — AGENTS.md §5 (workers/reconciliation.py).
Periodic 1%-sample reconciliation: compare SWS vs dept values for randomly sampled UBIDs.
Mismatches generate correction events back into the pipeline.

Fixes applied:
- UBIDs sampled from audit_ledger (not hardcoded test IDs)
- Mismatches generate correction events written to outbox
- Correction events are loop-guard marked to prevent echo
"""

import structlog

from synckar.workers.celery_app import celery_app

logger = structlog.get_logger()

# SWS canonical field → shop field mapping
SWS_TO_SHOP = {
    "registered_address": "Buss_Addr_Line1",
    "authorized_signatory": "Auth_Sign_Name",
    "primary_contact": "Contact_Phone",
    "employee_headcount": "Emp_Count",
    "operational_status": "Op_Status",
}

# SWS canonical field → factories field mapping
SWS_TO_FACTORY = {
    "registered_address": "factory_address",
    "authorized_signatory": "signatory_name",
    "primary_contact": "contact_number",
    "employee_headcount": "worker_count",
    "operational_status": "factory_status",
}

# Fields where SWS is authoritative (UNIVERSAL_DEMOGRAPHICS)
SWS_AUTHORITATIVE_FIELDS = {"registered_address", "authorized_signatory", "primary_contact"}


def _sample_ubids_from_db(sample_size: int) -> list[str]:
    """
    Sample UBIDs from the audit_ledger so we reconcile real traffic,
    not a hardcoded test list.
    Falls back to empty list if DB is unavailable.
    """
    from synckar import db
    try:
        conn = db.get_conn()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT DISTINCT ubid FROM audit_ledger ORDER BY random() LIMIT %s",
                (sample_size,),
            )
            rows = cursor.fetchall()
            return [row[0] for row in rows]
        finally:
            db.put_conn(conn)
    except Exception as e:
        logger.error("reconciliation_ubid_sample_failed", error=str(e))
        return []


def _emit_correction_event(
    ubid: str,
    field: str,
    correct_value: str,
    source_system: str,
    department: str,
) -> None:
    """
    Write a correction event to the outbox so the pipeline re-syncs the mismatch.
    Marks the write in loop_guard to prevent echo.
    """
    from uuid import uuid4
    from synckar.models.service_request import (
        CanonicalServiceRequest,
        RequestType,
        SourceSystem,
        derive_event_id,
    )
    from synckar.pipeline.outbox import write_to_outbox
    from synckar.pipeline import loop_guard

    FIELD_TO_REQUEST_TYPE = {
        "registered_address": RequestType.ADDRESS_CHANGE,
        "primary_contact": RequestType.ADDRESS_CHANGE,
        "authorized_signatory": RequestType.SIGNATORY_UPDATE,
        "employee_headcount": RequestType.CLOSURE_REQUEST,
        "operational_status": RequestType.CLOSURE_REQUEST,
    }

    try:
        src = SourceSystem(source_system)
    except ValueError:
        src = SourceSystem.SWS

    event_id = derive_event_id(ubid, field, None, correct_value)
    event = CanonicalServiceRequest(
        correlation_id=uuid4(),
        ubid=ubid,
        request_type=FIELD_TO_REQUEST_TYPE.get(field, RequestType.ADDRESS_CHANGE),
        source_system=src,
        source_event_id=f"reconcile-{event_id}",
        field_name=field,
        old_value=None,
        new_value=correct_value,
        raw_payload={"reconciliation": True, "department": department},
    )

    # Determine topic based on source
    topic_map = {
        "sws": "sws.changes",
        "shop_establishment": "dept.shop_establishment.changes",
        "factories": "dept.factories.changes",
    }
    topic = topic_map.get(source_system, "sws.changes")

    write_to_outbox(event, topic=topic)

    # Mark in loop_guard so the poller doesn't echo this back
    loop_guard.mark_write(department, ubid, field, correct_value)

    logger.info(
        "reconciliation_correction_emitted",
        ubid=ubid,
        field=field,
        source=source_system,
        target=department,
    )


@celery_app.task(name="synckar.workers.reconciliation.reconcile_sample")
def reconcile_sample(sample_size: int = 20):
    """
    Nightly reconciliation job.
    1. Randomly sample N UBIDs from audit_ledger (real traffic, not hardcoded)
    2. For each: compare SWS value vs dept value
    3. If mismatch: log AND generate correction event back into the pipeline
    """
    from synckar.adapters.sws.client import SWSClient
    from synckar.adapters.departments.shop_establishment.client import ShopEstablishmentClient
    from synckar.adapters.departments.factories.client import FactoriesClient

    sws = SWSClient()
    shop = ShopEstablishmentClient()
    factories = FactoriesClient()

    # Sample from real audit traffic — not hardcoded test IDs
    sample = _sample_ubids_from_db(sample_size)
    if not sample:
        logger.info("reconciliation_no_ubids_to_sample")
        return {"sampled": 0, "mismatches_found": 0, "details": []}

    mismatches = []
    corrections_emitted = 0

    for ubid in sample:
        try:
            sws_data = sws.get_business(ubid)
            if not sws_data:
                continue

            # ── Check Shop Establishment ──
            shop_data = shop.get_record(ubid)
            if shop_data:
                for sws_field, shop_field in SWS_TO_SHOP.items():
                    sws_val = str(sws_data.get(sws_field, ""))
                    shop_val = str(shop_data.get(shop_field, ""))
                    if sws_val and shop_val and sws_val != shop_val:
                        mismatch = {
                            "ubid": ubid,
                            "field": sws_field,
                            "sws_value": sws_val[:100],
                            "dept_value": shop_val[:100],
                            "department": "shop_establishment",
                        }
                        mismatches.append(mismatch)
                        logger.warning("reconciliation_mismatch", **mismatch)

                        # Emit correction: SWS is authoritative for UNIVERSAL_DEMOGRAPHICS
                        if sws_field in SWS_AUTHORITATIVE_FIELDS:
                            _emit_correction_event(
                                ubid=ubid,
                                field=sws_field,
                                correct_value=sws_val,
                                source_system="sws",
                                department="shop_establishment",
                            )
                            corrections_emitted += 1

            # ── Check Factories ──
            fact_data = factories.get_record(ubid)
            if fact_data:
                for sws_field, fact_field in SWS_TO_FACTORY.items():
                    sws_val = str(sws_data.get(sws_field, ""))
                    fact_val = str(fact_data.get(fact_field, ""))
                    if sws_val and fact_val and sws_val != fact_val:
                        mismatch = {
                            "ubid": ubid,
                            "field": sws_field,
                            "sws_value": sws_val[:100],
                            "dept_value": fact_val[:100],
                            "department": "factories",
                        }
                        mismatches.append(mismatch)
                        logger.warning("reconciliation_mismatch", **mismatch)

                        if sws_field in SWS_AUTHORITATIVE_FIELDS:
                            _emit_correction_event(
                                ubid=ubid,
                                field=sws_field,
                                correct_value=sws_val,
                                source_system="sws",
                                department="factories",
                            )
                            corrections_emitted += 1

        except Exception as e:
            logger.error("reconciliation_error", ubid=ubid, error=str(e))

    logger.info(
        "reconciliation_complete",
        sampled=len(sample),
        mismatches=len(mismatches),
        corrections_emitted=corrections_emitted,
    )

    return {
        "sampled": len(sample),
        "mismatches_found": len(mismatches),
        "corrections_emitted": corrections_emitted,
        "details": mismatches,
    }
