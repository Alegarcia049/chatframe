import logging

from app2.db.session import get_pool

logger = logging.getLogger(__name__)


async def ensure_schema() -> None:
    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id BIGSERIAL PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    platform TEXT,
                    sender_id TEXT,
                    message_id TEXT,
                    direction TEXT NOT NULL,
                    status TEXT NOT NULL,
                    retry_count INT NOT NULL DEFAULT 0,
                    latency_ms INT NULL,
                    inbound_text_len INT NULL,
                    outbound_text_len INT NULL,
                    error_type TEXT NULL,
                    error_message TEXT NULL,
                    metadata JSONB NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
            await cur.execute(
                "CREATE INDEX IF NOT EXISTS idx_audit_logs_trace_id ON audit_logs(trace_id)"
            )
        await conn.commit()

    logger.info("Audit schema ensured")
