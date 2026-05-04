"""Database connection pooling utilities."""

import threading

from psycopg2.pool import SimpleConnectionPool

from synckar.config import settings

_pool = None
_lock = threading.Lock()


def _init_pool() -> SimpleConnectionPool:
    global _pool
    if _pool is None:
        with _lock:
            if _pool is None:
                _pool = SimpleConnectionPool(
                    minconn=settings.database.pool_min,
                    maxconn=settings.database.pool_max,
                    dsn=settings.database.url,
                )
    return _pool


def get_conn():
    """Acquire a connection from the pool."""
    pool = _init_pool()
    return pool.getconn()


def put_conn(conn) -> None:
    """Return a connection to the pool."""
    if conn is None:
        return
    pool = _init_pool()
    pool.putconn(conn)


def close_pool() -> None:
    """Close all pooled connections."""
    global _pool
    if _pool is None:
        return
    _pool.closeall()
    _pool = None
