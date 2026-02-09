import logging
from typing import Dict, Optional

from app2.channels.base import BaseChannelClient

logger = logging.getLogger(__name__)


class FacebookChannelClient(BaseChannelClient):
    platform = "fb"

    def send_text(
        self,
        recipient_id: str,
        text: str,
        *,
        in_reply_to: Optional[str],
        metadata: Dict,
    ) -> None:
        logger.info(
            "channel_send platform=%s recipient_id=%s in_reply_to=%s text_len=%s metadata_keys=%s",
            self.platform,
            recipient_id,
            in_reply_to,
            len(text or ""),
            sorted(list((metadata or {}).keys())),
        )
