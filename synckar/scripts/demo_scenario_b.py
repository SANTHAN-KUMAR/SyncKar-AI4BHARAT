"""
Demo Scenario B: Department → SWS Propagation.
1. Update signatory in mock Factories for KA-TEST-0002
2. Wait for propagation to SWS
3. Query audit trail
"""

import sys
import time

import httpx

SWS_URL = "http://localhost:8000"
FACTORIES_URL = "http://localhost:8002"
SYNCKAR_URL = "http://localhost:18080"

UBID = "KA-TEST-0002"
NEW_SIGNATORY = "Rajesh Kumar Sharma"

POLL_INTERVAL = 2
MAX_WAIT = 90


def main():
    print("=" * 70)
    print("SCENARIO B: Department → SWS Propagation")
    print("=" * 70)
    print()

    # Step 1: Current state
    print("[1] Current state of KA-TEST-0002:")
    sws = httpx.get(f"{SWS_URL}/api/businesses/{UBID}").json()
    fact = httpx.get(f"{FACTORIES_URL}/api/records/by-ubid/{UBID}").json()

    print(f"  SWS signatory:       {sws.get('authorized_signatory')}")
    print(f"  Factories signatory: {fact.get('signatory_name')}")
    print()

    # Step 2: Update in Factories
    print(f"[2] Updating signatory in Factories to: '{NEW_SIGNATORY}'")
    resp = httpx.put(
        f"{FACTORIES_URL}/api/records/by-ubid/{UBID}",
        json={"signatory_name": NEW_SIGNATORY},
    )
    print(f"  Factories response: {resp.json().get('updated_fields')}")
    print()

    # Step 3: Wait for propagation to SWS
    print(f"[3] Waiting for SyncKar to propagate to SWS (up to {MAX_WAIT}s)...")
    sws_done = False
    elapsed = 0

    for i in range(MAX_WAIT // POLL_INTERVAL):
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        try:
            sws = httpx.get(f"{SWS_URL}/api/businesses/{UBID}").json()
            if sws.get("authorized_signatory") == NEW_SIGNATORY:
                sws_done = True
                print(f"  ✅ SWS propagation complete after {elapsed}s")
                break
        except Exception:
            pass

    if not sws_done:
        print(f"  ⚠ SWS propagation timeout after {MAX_WAIT}s")
    print()

    # Step 4: Verify
    print("[4] Final state:")
    sws = httpx.get(f"{SWS_URL}/api/businesses/{UBID}").json()
    fact = httpx.get(f"{FACTORIES_URL}/api/records/by-ubid/{UBID}").json()
    sws_sig = sws.get("authorized_signatory")
    fact_sig = fact.get("signatory_name")
    print(f"  SWS signatory:       {sws_sig}  {'✅' if sws_sig == NEW_SIGNATORY else '❌'}")
    print(f"  Factories signatory: {fact_sig}  {'✅' if fact_sig == NEW_SIGNATORY else '❌'}")
    print()

    # Step 5: Audit
    print("[5] Audit trail:")
    try:
        audit = httpx.get(f"{SYNCKAR_URL}/api/audit", params={"ubid": UBID}).json()
        entries = audit.get("audit_entries", [])
        if entries:
            for entry in entries[:5]:
                print(f"  [{entry.get('created_at')}] {entry.get('source_system')} → "
                      f"{entry.get('target_system')}: "
                      f"{entry.get('field_modified')} = '{entry.get('new_value', '')[:40]}'")
        else:
            print("  (no audit entries yet)")
    except Exception as e:
        print(f"  Could not query audit: {e}")

    print()
    print("=" * 70)
    print("SCENARIO B COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
