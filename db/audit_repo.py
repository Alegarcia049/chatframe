import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from app2.db.session import get_pool

logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    trace_id: str
    platform: Optional[str]
    sender_id: Optional[str]
    message_id: Optional[str]
    direction: str
    status: str
    retry_count: int = 0
    latency_ms: Optional[int] = None
    inbound_text_len: Optional[int] = None
    outbound_text_len: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


class AuditRepository:
    async def log_event(self, event: AuditEvent) -> None:
        try:
            pool = await get_pool()
            error_message = (event.error_message or "")[:500] or None
            payload_json = json.dumps(event.metadata or {}, ensure_ascii=False)

            async with pool.connection() as conn:
                async with conn.cursor() as cur:
                    await cur.execute(
                        """
                        INSERT INTO audit_logs (
                            trace_id, platform, sender_id, message_id,
                            direction, status, retry_count, latency_ms,
                            inbound_text_len, outbound_text_len,
                            error_type, error_message, metadata
                        ) VALUES (
                            %s, %s, %s, %s,
                            %s, %s, %s, %s,
                            %s, %s,
                            %s, %s, %s::jsonb
                        )
                        """,
                        (
                            event.trace_id,
                            event.platform,
                            event.sender_id,
                            event.message_id,
                            event.direction,
                            event.status,
                            event.retry_count,
                            event.latency_ms,
                            event.inbound_text_len,
                            event.outbound_text_len,
                            event.error_type,
                            error_message,
                            payload_json,
                        ),
                    )
                await conn.commit()
        except Exception as exc:
            logger.error("audit_log_failed trace_id=%s status=%s err=%s", event.trace_id, event.status, exc)
