import asyncio
import logging
import os
import time
import uuid
from typing import Any, Dict, Optional

from app2.agents.langgraph_runtime import LangGraphAgentRuntime
from app2.channels.router import send_text
from app2.db.audit import ensure_schema
from app2.db.audit_repo import AuditEvent, AuditRepository
from app2.llm.factory import UnsupportedProviderError
from app2.worker.queue import (
    dequeue_message,
    enqueue_dead,
    enqueue_message,
    mark_processed_once,
)

logger = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

_REQUIRED_FIELDS = ("platform", "sender_id", "text", "message_id")
_audit_repo = AuditRepository()


def _is_valid_message(payload: Dict[str, Any]) -> bool:
    return all(payload.get(field) for field in _REQUIRED_FIELDS)


def _trace_id(payload: Dict[str, Any]) -> str:
    if payload.get("trace_id"):
        return str(payload["trace_id"])
    platform = payload.get("platform") or "unknown"
    message_id = payload.get("message_id")
    return f"{platform}:{message_id}" if message_id else str(uuid.uuid4())


async def _audit(event: AuditEvent) -> None:
    await _audit_repo.log_event(event)
    logger.info(
        "audit_event trace_id=%s status=%s direction=%s retry=%s",
        event.trace_id,
        event.status,
        event.direction,
        event.retry_count,
    )


async def _run_agent_stream(
    agent: LangGraphAgentRuntime,
    text: str,
    sender_id: str,
    platform: str,
) -> str:
    chunks = []

    try:
        stream = agent.respond_stream(text, sender_id=sender_id, platform=platform)
    except TypeError:
        # Compatibilidad con runtime que aún no acepta sender/platform.
        stream = agent.respond_stream(text)

    async for chunk in stream:
        if chunk == "__END__":
            continue
        chunks.append(chunk)

    return "".join(chunks)


async def _process_message(agent: LangGraphAgentRuntime, payload: Dict[str, Any]) -> None:
    trace_id = _trace_id(payload)

    if not _is_valid_message(payload):
        logger.warning("Skipping invalid payload (missing required fields): %s", payload)
        await _audit(
            AuditEvent(
                trace_id=trace_id,
                platform=payload.get("platform"),
                sender_id=payload.get("sender_id"),
                message_id=payload.get("message_id"),
                direction="internal",
                status="send_failed",
                retry_count=int(payload.get("_retry_count", 0)),
                error_type="ValidationError",
                error_message="Missing required fields",
                metadata=payload.get("metadata") or {},
            )
        )
        return

    platform = str(payload["platform"])
    sender_id = str(payload["sender_id"])
    message_id = str(payload["message_id"])
    text = str(payload["text"])
    metadata = payload.get("metadata") or {}
    retry_count = int(payload.get("_retry_count", 0))
    started_at = time.monotonic()

    await _audit(
        AuditEvent(
            trace_id=trace_id,
            platform=platform,
            sender_id=sender_id,
            message_id=message_id,
            direction="internal",
            status="processing",
            retry_count=retry_count,
            inbound_text_len=len(text),
            metadata=metadata,
        )
    )

    # Idempotencia inbound por message_id (solo primer intento).
    if retry_count == 0:
        is_new = mark_processed_once(platform=platform, message_id=message_id, ttl_seconds=86400)
        if not is_new:
            logger.info("Skipping duplicated inbound message: platform=%s message_id=%s", platform, message_id)
            await _audit(
                AuditEvent(
                    trace_id=trace_id,
                    platform=platform,
                    sender_id=sender_id,
                    message_id=message_id,
                    direction="internal",
                    status="skipped_idempotent",
                    retry_count=retry_count,
                    inbound_text_len=len(text),
                    metadata=metadata,
                )
            )
            return

    final_text = await _run_agent_stream(agent, text=text, sender_id=sender_id, platform=platform)
    latency_ms = int((time.monotonic() - started_at) * 1000)

    send_text(
        platform=platform,
        recipient_id=sender_id,
        text=final_text,
        in_reply_to=message_id,
        metadata=metadata,
    )

    await _audit(
        AuditEvent(
            trace_id=trace_id,
            platform=platform,
            sender_id=sender_id,
            message_id=message_id,
            direction="outbound",
            status="processed",
            retry_count=retry_count,
            latency_ms=latency_ms,
            inbound_text_len=len(text),
            outbound_text_len=len(final_text),
            metadata=metadata,
        )
    )

    logger.info(
        "Processed message_id=%s platform=%s sender_id=%s final_text_len=%s trace_id=%s",
        message_id,
        platform,
        sender_id,
        len(final_text),
        trace_id,
    )


def _next_backoff(current: int) -> int:
    return min(max(1, current * 2), 30)


async def run_worker() -> None:
    logger.info("Worker started.")

    try:
        await ensure_schema()
    except Exception as exc:
        logger.error("Audit schema ensure failed (best-effort): %s", exc)

    agent: Optional[LangGraphAgentRuntime] = None
    startup_backoff = 1

    while True:
        if agent is None:
            try:
                agent = LangGraphAgentRuntime()
                await agent.start_session()
                startup_backoff = 1
                logger.info("Worker agent ready.")
            except UnsupportedProviderError as exc:
                logger.error("Agent not ready (provider/config): %s", exc)
                await asyncio.sleep(startup_backoff)
                startup_backoff = _next_backoff(startup_backoff)
                continue
            except Exception as exc:
                logger.exception("Agent initialization failed: %s", exc)
                await asyncio.sleep(startup_backoff)
                startup_backoff = _next_backoff(startup_backoff)
                continue

        payload = dequeue_message(blocking=True, timeout=5)
        if payload is None:
            continue

        trace_id = _trace_id(payload)

        try:
            await _process_message(agent, payload)
        except UnsupportedProviderError as exc:
            logger.error("Agent became not ready during processing: %s", exc)
            payload["trace_id"] = trace_id
            enqueue_message(payload)
            await agent.stop()
            agent = None
            await asyncio.sleep(startup_backoff)
            startup_backoff = _next_backoff(startup_backoff)
        except Exception as exc:
            retry_count = int(payload.get("_retry_count", 0)) + 1
            max_retries = int(os.getenv("WORKER_MAX_RETRIES", "5"))
            backoff = min(2 ** retry_count, 30)

            logger.exception(
                "Processing/send failed trace_id=%s message_id=%s retry=%s/%s error=%s",
                trace_id,
                payload.get("message_id"),
                retry_count,
                max_retries,
                exc,
            )

            await _audit(
                AuditEvent(
                    trace_id=trace_id,
                    platform=payload.get("platform"),
                    sender_id=payload.get("sender_id"),
                    message_id=payload.get("message_id"),
                    direction="outbound",
                    status="send_failed",
                    retry_count=retry_count,
                    inbound_text_len=len(payload.get("text") or ""),
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    metadata=payload.get("metadata") or {},
                )
            )

            if retry_count <= max_retries:
                payload["_retry_count"] = retry_count
                payload["trace_id"] = trace_id
                await asyncio.sleep(backoff)
                enqueue_message(payload)
            else:
                payload["_dead_reason"] = str(exc)
                payload["trace_id"] = trace_id
                enqueue_dead(payload)
                await _audit(
                    AuditEvent(
                        trace_id=trace_id,
                        platform=payload.get("platform"),
                        sender_id=payload.get("sender_id"),
                        message_id=payload.get("message_id"),
                        direction="internal",
                        status="deadletter",
                        retry_count=retry_count,
                        inbound_text_len=len(payload.get("text") or ""),
                        error_type=type(exc).__name__,
                        error_message=str(exc),
                        metadata=payload.get("metadata") or {},
                    )
                )


if __name__ == "__main__":
    asyncio.run(run_worker())
