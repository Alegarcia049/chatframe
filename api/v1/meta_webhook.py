import asyncio
import json
import logging
import os
import uuid
from typing import Any, Dict, List, Literal, Optional, Tuple, TypedDict

from fastapi import APIRouter, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from app2.db.audit_repo import AuditEvent, AuditRepository
from app2.worker.queue import enqueue_message

logger = logging.getLogger(__name__)

router = APIRouter(tags=["meta-webhook"])
_audit_repo = AuditRepository()

Platform = Literal["wa", "ig", "fb"]


class NormalizedMessage(TypedDict):
    platform: Platform
    sender_id: str
    message_id: str
    text: str
    timestamp: str
    metadata: Dict[str, Any]


class IgnoredEvent(TypedDict):
    platform: Platform
    reason: str
    message_id: Optional[str]
    sender_id: Optional[str]
    metadata: Dict[str, Any]


def parse_whatsapp(payload: Dict[str, Any]) -> List[NormalizedMessage]:
    messages, _ = _parse_whatsapp_with_ignored(payload)
    return messages


def parse_messenger(payload: Dict[str, Any]) -> List[NormalizedMessage]:
    messages, _ = _parse_messenger_with_ignored(payload, default_platform="fb")
    return messages


def parse_instagram(payload: Dict[str, Any]) -> List[NormalizedMessage]:
    messages, _ = _parse_messenger_with_ignored(payload, default_platform="ig")
    return messages


def parse_meta_payload(payload: Dict[str, Any]) -> List[NormalizedMessage]:
    messages, _ = parse_meta_payload_detailed(payload)
    return messages


def parse_meta_payload_detailed(payload: Dict[str, Any]) -> Tuple[List[NormalizedMessage], List[IgnoredEvent]]:
    obj = (payload.get("object") or "").lower()
    if obj == "whatsapp_business_account":
        return _parse_whatsapp_with_ignored(payload)
    if obj == "instagram":
        return _parse_messenger_with_ignored(payload, default_platform="ig")
    # page and unknown objects default to messenger parsing with fb baseline
    return _parse_messenger_with_ignored(payload, default_platform="fb")


def _parse_whatsapp_with_ignored(payload: Dict[str, Any]) -> Tuple[List[NormalizedMessage], List[IgnoredEvent]]:
    normalized: List[NormalizedMessage] = []
    ignored: List[IgnoredEvent] = []

    for entry in payload.get("entry", []) or []:
        for change in entry.get("changes", []) or []:
            value = change.get("value", {})
            if value.get("messaging_product") != "whatsapp":
                continue

            contacts = {c.get("wa_id"): c for c in value.get("contacts", []) if c.get("wa_id")}

            for msg in value.get("messages", []) or []:
                sender_id = msg.get("from")
                message_id = msg.get("id")
                msg_type = msg.get("type")
                text = (msg.get("text") or {}).get("body")
                metadata = {
                    "entry_id": entry.get("id"),
                    "object": payload.get("object"),
                    "contact": contacts.get(sender_id),
                    "change_field": change.get("field"),
                    "message_type": msg_type,
                }

                if msg_type != "text":
                    ignored.append(
                        {
                            "platform": "wa",
                            "reason": f"unsupported_type:{msg_type}",
                            "message_id": message_id,
                            "sender_id": sender_id,
                            "metadata": metadata,
                        }
                    )
                    continue

                if not sender_id or not text:
                    ignored.append(
                        {
                            "platform": "wa",
                            "reason": "missing_sender_or_text",
                            "message_id": message_id,
                            "sender_id": sender_id,
                            "metadata": metadata,
                        }
                    )
                    continue

                normalized.append(
                    {
                        "platform": "wa",
                        "sender_id": str(sender_id),
                        "message_id": str(message_id or ""),
                        "text": str(text),
                        "timestamp": str(msg.get("timestamp") or ""),
                        "metadata": metadata,
                    }
                )

    return normalized, ignored


def _parse_messenger_with_ignored(
    payload: Dict[str, Any],
    default_platform: Platform,
) -> Tuple[List[NormalizedMessage], List[IgnoredEvent]]:
    normalized: List[NormalizedMessage] = []
    ignored: List[IgnoredEvent] = []

    for entry in payload.get("entry", []) or []:
        for event in entry.get("messaging", []) or []:
            platform = _detect_messenger_platform(default_platform, event, entry)
            message = event.get("message") or {}
            message_id = message.get("mid")
            sender_id = (event.get("sender") or {}).get("id")
            text = message.get("text")

            metadata = {
                "entry_id": entry.get("id"),
                "object": payload.get("object"),
                "recipient": (event.get("recipient") or {}).get("id"),
                "is_echo": message.get("is_echo"),
                "has_attachments": bool(message.get("attachments")),
            }

            # receipts, delivery, read, optin, postback, etc.
            if not message:
                ignored.append(
                    {
                        "platform": platform,
                        "reason": "non_message_event",
                        "message_id": None,
                        "sender_id": sender_id,
                        "metadata": metadata,
                    }
                )
                continue

            if not text:
                ignored.append(
                    {
                        "platform": platform,
                        "reason": "message_without_text",
                        "message_id": message_id,
                        "sender_id": sender_id,
                        "metadata": metadata,
                    }
                )
                continue

            if not sender_id:
                ignored.append(
                    {
                        "platform": platform,
                        "reason": "missing_sender",
                        "message_id": message_id,
                        "sender_id": sender_id,
                        "metadata": metadata,
                    }
                )
                continue

            normalized.append(
                {
                    "platform": platform,
                    "sender_id": str(sender_id),
                    "message_id": str(message_id or ""),
                    "text": str(text),
                    "timestamp": str(event.get("timestamp") or ""),
                    "metadata": metadata,
                }
            )

    return normalized, ignored

def _validate_optional_header(x_webhook_token: Optional[str]) -> None:
    expected = os.getenv("META_WEBHOOK_HEADER_TOKEN", "").strip()
    if not expected:
        return
    if not x_webhook_token or x_webhook_token != expected:
        raise HTTPException(status_code=401, detail="Invalid webhook header token")


def _schedule_audit(event: AuditEvent) -> None:
    asyncio.create_task(_audit_repo.log_event(event))


@router.get("/webhook")
async def verify_webhook(request: Request):
    mode = request.query_params.get("hub.mode")
    token = request.query_params.get("hub.verify_token")
    challenge = request.query_params.get("hub.challenge")

    expected = os.getenv("META_VERIFY_TOKEN", "")

    if mode == "subscribe" and expected and token == expected and challenge is not None:
        return PlainTextResponse(content=challenge, status_code=200)

    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    x_webhook_token: Optional[str] = Header(default=None, alias="X-Webhook-Token"),
):
    _validate_optional_header(x_webhook_token)

    raw = await request.body()
    if not raw:
        return Response(status_code=200)

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    parsed_messages, ignored_events = parse_meta_payload_detailed(payload)

    for message in parsed_messages:
        message_id = message.get("message_id")
        trace_id = f"{message.get('platform', 'unknown')}:{message_id}" if message_id else str(uuid.uuid4())

        if not message_id:
            logger.info(
                "ignored_event trace_id=%s reason=%s platform=%s",
                trace_id,
                "missing_message_id",
                message.get("platform"),
            )
            _schedule_audit(
                AuditEvent(
                    trace_id=trace_id,
                    platform=message.get("platform"),
                    sender_id=message.get("sender_id"),
                    message_id=None,
                    direction="inbound",
                    status="ignored",  # asegurar que existe en tu modelo
                    retry_count=0,
                    inbound_text_len=len(message.get("text") or ""),
                    error_type="MissingMessageId",
                    error_message="Message has no message_id; not enqueued",
                    metadata=message.get("metadata") or {},
                )
            )
            continue

        message["trace_id"] = trace_id
        enqueue_message(message)

        _schedule_audit(
            AuditEvent(
                trace_id=trace_id,
                platform=message.get("platform"),
                sender_id=message.get("sender_id"),
                message_id=message_id,
                direction="inbound",
                status="enqueued",
                retry_count=0,
                inbound_text_len=len(message.get("text") or ""),
                metadata=message.get("metadata") or {},
            )
        )
        logger.info("audit_event trace_id=%s status=%s direction=%s", trace_id, "enqueued", "inbound")

    for ignored in ignored_events:
        ignored_message_id = ignored.get("message_id")
        trace_id = f"{ignored.get('platform', 'unknown')}:{ignored_message_id}" if ignored_message_id else str(uuid.uuid4())

        logger.info("ignored_event trace_id=%s platform=%s reason=%s", trace_id, ignored.get("platform"), ignored.get("reason"))
        _schedule_audit(
            AuditEvent(
                trace_id=trace_id,
                platform=ignored.get("platform"),
                sender_id=ignored.get("sender_id"),
                message_id=ignored_message_id,
                direction="inbound",
                status="ignored",  # asegurar que existe
                retry_count=0,
                error_type="IgnoredEvent",
                error_message=str(ignored.get("reason")),
                metadata=ignored.get("metadata") or {},
            )
        )

