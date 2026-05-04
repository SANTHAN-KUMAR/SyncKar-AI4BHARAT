"""
Demo Scenario A: SWS → Department Propagation.
1. Update address for KA-TEST-0001 in mock SWS
2. Wait for propagation to Shop Est + Factories independently
3. Query audit trail — show audit rows with same correlation_id
"""

import sys
import time

import httpx

SWS_URL = "http://localhost:8000"
SHOP_URL = "http://localhost:8001"
FACTORIES_URL = "http://localhost:8002"
SYNCKAR_URL = "http://localhost:18080"

UBID = "KA-TEST-0001"
NEW_ADDRESS = "999 New MG Road, Indiranagar, Bangalore 560038"

# Poll every 2s for up to 90s (covers worst-case: poll 10s + drain 3s + Kafka + Celery queue)
POLL_INTERVAL = 2
MAX_WAIT = 90


def main():
    print("=" * 70)
    print("SCENARIO A: SWS → Department Propagation")
    print("=" * 70)
    print()

    # Step 1: Show current state
    print("[1] Current state of KA-TEST-0001 across all systems:")
    sws = httpx.get(f"{SWS_URL}/api/businesses/{UBID}").json()
    shop = httpx.get(f"{SHOP_URL}/api/records/by-ubid/{UBID}").json()
    fact = httpx.get(f"{FACTORIES_URL}/api/records/by-ubid/{UBID}").json()

    print(f"  SWS address:       {sws.get('registered_address')}")
    print(f"  Shop Est address:  {shop.get('Buss_Addr_Line1')}")
    print(f"  Factories address: {fact.get('factory_address')}")
    print()

    # Step 2: Update address in SWS
    print(f"[2] Updating address in SWS to: '{NEW_ADDRESS}'")
    resp = httpx.put(
        f"{SWS_URL}/api/businesses/{UBID}",
        json={"registered_address": NEW_ADDRESS},
    )
    print(f"  SWS response: {resp.json().get('updated_fields')}")
    print()

    # Step 3: Wait for propagation — track each target independently
    print(f"[3] Waiting for SyncKar to propagate (up to {MAX_WAIT}s)...")
    shop_done = False
    fact_done = False
    elapsed = 0

    for i in range(MAX_WAIT // POLL_INTERVAL):
        time.sleep(POLL_INTERVAL)
        elapsed += POLL_INTERVAL
        try:
            if not shop_done:
                shop = httpx.get(f"{SHOP_URL}/api/records/by-ubid/{UBID}").json()
                # Shop Est applies truncate(120) transform
                if shop.get("Buss_Addr_Line1") == NEW_ADDRESS[:120]:
                    shop_done = True
                    print(f"  ✅ Shop Establishment propagated after {elapsed}s")

            if not fact_done:
                fact = httpx.get(f"{FACTORIES_URL}/api/records/by-ubid/{UBID}").json()
                if fact.get("factory_address") == NEW_ADDRESS:
                    fact_done = True
                    print(f"  ✅ Factories propagated after {elapsed}s")

        except Exception:
            pass

        if shop_done and fact_done:
            break

    if not shop_done:
        print(f"  ⚠ Shop Establishment propagation timeout after {MAX_WAIT}s")
    if not fact_done:
        print(f"  ⚠ Factories propagation timeout after {MAX_WAIT}s")
    print()

    # Step 4: Verify final state
    print("[4] Final state of KA-TEST-0001:")
    sws = httpx.get(f"{SWS_URL}/api/businesses/{UBID}").json()
    shop = httpx.get(f"{SHOP_URL}/api/records/by-ubid/{UBID}").json()
    fact = httpx.get(f"{FACTORIES_URL}/api/records/by-ubid/{UBID}").json()

    sws_addr = sws.get("registered_address")
    shop_addr = shop.get("Buss_Addr_Line1")
    fact_addr = fact.get("factory_address")

    print(f"  SWS address:       {sws_addr}")
    print(f"  Shop Est address:  {shop_addr}  {'✅' if shop_addr == NEW_ADDRESS[:120] else '❌'}")
    print(f"  Factories address: {fact_addr}  {'✅' if fact_addr == NEW_ADDRESS else '❌'}")
    print()

    # Step 5: Query audit trail
    print("[5] Audit trail for KA-TEST-0001:")
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
    print("SCENARIO A COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
