from abc import ABC, abstractmethod
from typing import Dict, Literal, Optional

Platform = Literal["wa", "ig", "fb"]


class BaseChannelClient(ABC):
    platform: Platform

    @abstractmethod
    def send_text(
        self,
        recipient_id: str,
        text: str,
        *,
        in_reply_to: Optional[str],
        metadata: Dict,
    ) -> None:
        raise NotImplementedError
