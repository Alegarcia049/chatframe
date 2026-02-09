import logging
from typing import Any, Dict

logger = logging.getLogger(__name__)


def send_to_meta(platform: str, sender_id: str, text: str, metadata: Dict[str, Any]) -> None:
    """Stub transport to Meta channels. TODO Paso 8: integrate real Graph endpoints."""
    logger.info(
        "[meta_client stub] send platform=%s sender_id=%s text=%s metadata_keys=%s",
        platform,
        sender_id,
        (text or "")[:120],
        sorted(list((metadata or {}).keys())),
    )
