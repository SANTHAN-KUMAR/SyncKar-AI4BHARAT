"""
Reset SyncKar runtime state between demo runs.

Clears:
  - Redis: idempotency keys, watermarks, conflict windows, circuit breaker state
  - PostgreSQL outbox: marks all PENDING/PUBLISHED rows as RESET (leaves audit intact)

Does NOT touch:
  - audit_ledger (append-only, C6)
  - Mock system in-memory data (restart containers to reset those)

Usage:
  python scripts/reset_state.py
  python scripts/reset_state.py --redis-url redis://localhost:6379/0 --db-url postgresql://...
"""

import argparse
import sys

import psycopg2
import redis as redis_lib


REDIS_URL = "redis://localhost:6379/0"
DB_URL = "postgresql://synckar_app:synckar_app@localhost:15432/synckar"

# Redis key patterns to flush (watermarks, idempotency, conflict windows, circuit breakers)
REDIS_KEY_PATTERNS = [
    "sws:watermark",
    "factories:watermark",
    "shop_establishment:watermark",
    "idem:*",
    "conflict_window:*",
    "circuit:*",
    "rate_limit:*",
]


def reset_redis(redis_url: str) -> int:
    """Delete all SyncKar runtime keys from Redis. Returns count of deleted keys."""
    r = redis_lib.Redis.from_url(redis_url, decode_responses=True)
    deleted = 0
    for pattern in REDIS_KEY_PATTERNS:
        keys = r.keys(pattern)
        if keys:
            deleted += r.delete(*keys)
            print(f"  Deleted {len(keys)} keys matching '{pattern}'")
    return deleted


def reset_outbox(db_url: str) -> int:
    """
    Delete PENDING and PUBLISHED outbox rows so stale events are not re-drained.
    Returns count of deleted rows.
    """
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM outbox WHERE status IN ('PENDING', 'PUBLISHED')")
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def reset_dlq(db_url: str) -> int:
    """Delete PENDING DLQ rows from previous runs."""
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM dead_letter_queue WHERE status = 'PENDING'")
    def reset_poller_state(db_url: str) -> int:
        """Delete poller_state rows (watermarks)."""
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM poller_state")
        count = cursor.rowcount
        conn.commit()
        conn.close()
        return count
    count = cursor.rowcount
    conn.commit()
    conn.close()
    return count


def main():
    parser = argparse.ArgumentParser(description="Reset SyncKar runtime state between demo runs")
    parser.add_argument("--redis-url", default=REDIS_URL)
    parser.add_argument("--db-url", default=DB_URL)
    parser.add_argument("--skip-redis", action="store_true")
    parser.add_argument("--skip-db", action="store_true")
    args = parser.parse_args()

    print("SyncKar — Resetting runtime state")
    print()

    if not args.skip_redis:
        print(f"Redis ({args.redis_url}):")
        try:
            deleted = reset_redis(args.redis_url)
            print(f"  Total keys deleted: {deleted}")
        except Exception as e:
            print(f"  ERROR: {e}")
            sys.exit(1)
        print()

    if not args.skip_db:
        print(f"PostgreSQL ({args.db_url}):")
        try:
            outbox_count = reset_outbox(args.db_url)
            print(f"  Outbox rows deleted: {outbox_count}")
            dlq_count = reset_dlq(args.db_url)
            print(f"  DLQ rows deleted: {dlq_count}")
            poller_count = reset_poller_state(args.db_url)
            print(f"  Poller state rows deleted: {poller_count}")
        except Exception as e:
            print(f"  ERROR: {e}")
            sys.exit(1)
        print()

    print("Reset complete. You can now re-run seed_data.py and the demo scenarios.")
    print()
    print("NOTE: audit_ledger is append-only and was NOT cleared (BSA 2023 compliance).")
    print("NOTE: Mock system in-memory data persists until containers are restarted.")


if __name__ == "__main__":
    main()
