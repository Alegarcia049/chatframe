import json
import logging
import os
from queue import Empty, Queue
from typing import Dict, Optional

logger = logging.getLogger(__name__)

_MEMORY_QUEUE: Queue = Queue()
_MEMORY_DEAD_QUEUE: Queue = Queue()
_MEMORY_PROCESSED_KEYS = set()
_REDIS_CLIENT = None


def get_backend() -> str:
    return os.getenv("QUEUE_BACKEND", "memory").strip().lower()


def _get_redis_client():
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    try:
        import redis  # type: ignore
    except Exception as exc:
        raise RuntimeError("QUEUE_BACKEND=redis requires 'redis' package installed") from exc

    _REDIS_CLIENT = redis.Redis.from_url(redis_url, decode_responses=True)
    return _REDIS_CLIENT


def enqueue_message(payload: Dict) -> None:
    backend = get_backend()

    if backend == "memory":
        _MEMORY_QUEUE.put(payload)
        logger.info("Queued message using memory backend: %s", payload.get("message_id"))
        return

    if backend == "redis":
        queue_name = os.getenv("QUEUE_NAME", "meta_messages")
        client = _get_redis_client()
        # Producer pushes left
        client.lpush(queue_name, json.dumps(payload, ensure_ascii=False))
        logger.info("Queued message in redis list '%s': %s", queue_name, payload.get("message_id"))
        return

    raise RuntimeError(f"Unsupported QUEUE_BACKEND={backend}. Use memory|redis")


def enqueue_dead(payload: Dict) -> None:
    backend = get_backend()

    if backend == "memory":
        _MEMORY_DEAD_QUEUE.put(payload)
        logger.error("Moved message to memory DLQ: %s", payload.get("message_id"))
        return

    if backend == "redis":
        queue_name = os.getenv("QUEUE_NAME", "meta_messages")
        dead_name = f"{queue_name}:dead"
        client = _get_redis_client()
        client.lpush(dead_name, json.dumps(payload, ensure_ascii=False))
        logger.error("Moved message to redis DLQ '%s': %s", dead_name, payload.get("message_id"))
        return

    raise RuntimeError(f"Unsupported QUEUE_BACKEND={backend}. Use memory|redis")


def dequeue_message(blocking: bool = True, timeout: int = 5) -> Optional[Dict]:
    backend = get_backend()

    if backend == "memory":
        try:
            if blocking:
                return _MEMORY_QUEUE.get(timeout=timeout)
            return _MEMORY_QUEUE.get_nowait()
        except Empty:
            return None

    if backend == "redis":
        queue_name = os.getenv("QUEUE_NAME", "meta_messages")
        client = _get_redis_client()

        # Consumer pops right
        if blocking:
            item = client.brpop(queue_name, timeout=timeout)
            if not item:
                return None
            _, raw_payload = item
        else:
            raw_payload = client.rpop(queue_name)
            if not raw_payload:
                return None

        try:
            return json.loads(raw_payload)
        except json.JSONDecodeError:
            logger.error("Invalid JSON in queue payload: %s", raw_payload)
            return None

    raise RuntimeError(f"Unsupported QUEUE_BACKEND={backend}. Use memory|redis")


def mark_processed_once(platform: str, message_id: str, ttl_seconds: int = 86400) -> bool:
    """Return True only the first time a given inbound message is seen."""
    backend = get_backend()
    key = f"processed:{platform}:{message_id}"

    if backend == "memory":
        if key in _MEMORY_PROCESSED_KEYS:
            return False
        _MEMORY_PROCESSED_KEYS.add(key)
        return True

    if backend == "redis":
        client = _get_redis_client()
        created = client.set(key, "1", nx=True, ex=ttl_seconds)
        return bool(created)

    raise RuntimeError(f"Unsupported QUEUE_BACKEND={backend}. Use memory|redis")
