import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)

_POOL = None


def is_audit_enabled() -> bool:
    return os.getenv("AUDIT_ENABLED", "true").strip().lower() in {"1", "true", "yes", "on"}


def _get_database_url() -> Optional[str]:
    return os.getenv("AUDIT_DATABASE_URL") or os.getenv("DATABASE_URL")


async def get_pool():
    global _POOL
    if _POOL is not None:
        return _POOL

    if not is_audit_enabled():
        raise RuntimeError("Audit disabled by AUDIT_ENABLED")

    db_url = _get_database_url()
    if not db_url:
        raise RuntimeError("AUDIT_DATABASE_URL/DATABASE_URL is not configured")

    try:
        from psycopg_pool import AsyncConnectionPool  # type: ignore
    except Exception as exc:
        raise RuntimeError("psycopg_pool is required for PostgreSQL audit logging") from exc

    _POOL = AsyncConnectionPool(conninfo=db_url, min_size=1, max_size=5, open=False)
    await _POOL.open()
    logger.info("Audit PostgreSQL pool initialized")
    return _POOL


async def close_pool() -> None:
    global _POOL
    if _POOL is not None:
        await _POOL.close()
        _POOL = None
        logger.info("Audit PostgreSQL pool closed")
