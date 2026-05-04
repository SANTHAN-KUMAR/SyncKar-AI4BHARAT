"""
Demo Scenario C: Conflict Detection & Resolution.
1. Simultaneously update address in SWS AND Factories for KA-TEST-0003
2. Wait for conflict detection
3. Verify: SWS wins (UNIVERSAL_DEMOGRAPHICS policy)
4. Show both values preserved in conflict log
"""

import sys
import time
import threading

import httpx

SWS_URL = "http://localhost:8000"
FACTORIES_URL = "http://localhost:8002"
SYNCKAR_URL = "http://localhost:18080"

UBID = "KA-TEST-0003"
SWS_ADDRESS = "111 MG Road, Updated by SWS, Bangalore 560001"
DEPT_ADDRESS = "222 Factory Lane, Updated by Dept, Bangalore 560002"


def main():
    print("=" * 70)
    print("SCENARIO C: Conflict Detection & Resolution")
    print("=" * 70)
    print()

    # Step 1: Current state
    print("[1] Current state of KA-TEST-0003:")
    sws = httpx.get(f"{SWS_URL}/api/businesses/{UBID}").json()
    fact = httpx.get(f"{FACTORIES_URL}/api/records/by-ubid/{UBID}").json()
    print(f"  SWS address:       {sws.get('registered_address')}")
    print(f"  Factories address: {fact.get('factory_address')}")
    print()

    # Step 2: Simultaneous updates
    print("[2] Triggering SIMULTANEOUS address updates:")
    print(f"  SWS:       '{SWS_ADDRESS}'")
    print(f"  Factories: '{DEPT_ADDRESS}'")

    def update_sws():
        httpx.put(
            f"{SWS_URL}/api/businesses/{UBID}",
            json={"registered_address": SWS_ADDRESS},
        )

    def update_factories():
        httpx.put(
            f"{FACTORIES_URL}/api/records/by-ubid/{UBID}",
            json={"factory_address": DEPT_ADDRESS},
        )

    t1 = threading.Thread(target=update_sws)
    t2 = threading.Thread(target=update_factories)
    t1.start()
    t2.start()
    t1.join()
    t2.join()
    print("  Both updates submitted")
    print()

    # Step 3: Wait for conflict resolution
    print("[3] Waiting for SyncKar conflict detection & resolution...")
    time.sleep(15)  # Wait for polling + propagation cycle

    # Step 4: Check conflict log
    print("[4] Conflict log:")
    try:
        conflicts = httpx.get(
            f"{SYNCKAR_URL}/api/dlq/conflicts",
            params={"ubid": UBID},
        ).json()
        for conflict in conflicts.get("conflicts", []):
            print(f"  UBID: {conflict.get('ubid')}")
            print(f"  Field: {conflict.get('field')}")
            print(f"  Policy Applied: {conflict.get('policy_applied')}")
            print(f"  Winning Value: {conflict.get('winning_value', '')[:50]}")
            print(f"  Losing Value: {conflict.get('losing_value', '')[:50]}")
            print(f"  Temporal Confidence: {conflict.get('temporal_confidence')}")
            print()
    except Exception as e:
        print(f"  Could not query conflicts: {e}")

    # Step 5: Verify field_name = registered_address → SWS_WINS policy
    print("[5] Expected resolution for 'registered_address':")
    print("  Category: UNIVERSAL_DEMOGRAPHICS → Policy: SWS_WINS")
    print(f"  Winner: SWS value = '{SWS_ADDRESS[:40]}...'")
    print(f"  Loser (preserved): Dept value = '{DEPT_ADDRESS[:40]}...'")
    print()

    # Step 6: Final state
    print("[6] Final state:")
    sws = httpx.get(f"{SWS_URL}/api/businesses/{UBID}").json()
    fact = httpx.get(f"{FACTORIES_URL}/api/records/by-ubid/{UBID}").json()
    print(f"  SWS address:       {sws.get('registered_address')}")
    print(f"  Factories address: {fact.get('factory_address')}")
    print()

    # Step 7: Audit verification
    print("[7] BSA 2023 Audit Verification:")
    try:
        audit = httpx.get(f"{SYNCKAR_URL}/api/audit", params={"ubid": UBID}).json()
        entries = audit.get("audit_entries", [])
        if entries:
            latest = entries[0]
            audit_id = latest.get("audit_id")
            verify = httpx.get(f"{SYNCKAR_URL}/api/audit/verify/{audit_id}").json()
            print(f"  Audit ID: {audit_id}")
            print(f"  RSA Signature Valid: {verify.get('signature_valid')}")
            print(f"  BSA 2023 Compliant: {verify.get('bsa_2023_compliant')}")
    except Exception as e:
        print(f"  Could not verify: {e}")

    print()
    print("=" * 70)
    print("SCENARIO C COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
