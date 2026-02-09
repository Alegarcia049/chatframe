from app2.channels.base import BaseChannelClient, Platform
from app2.channels.facebook import FacebookChannelClient
from app2.channels.instagram import InstagramChannelClient
from app2.channels.whatsapp import WhatsAppChannelClient

_CLIENTS = {
    "wa": WhatsAppChannelClient(),
    "ig": InstagramChannelClient(),
    "fb": FacebookChannelClient(),
}


def get_client(platform: Platform) -> BaseChannelClient:
    try:
        return _CLIENTS[platform]
    except KeyError as exc:
        raise ValueError(f"Unsupported platform={platform}") from exc


def send_text(
    platform: Platform,
    recipient_id: str,
    text: str,
    in_reply_to: str = None,
    metadata: dict = None,
) -> None:
    client = get_client(platform)
    client.send_text(
        recipient_id=recipient_id,
        text=text,
        in_reply_to=in_reply_to,
        metadata=metadata or {},
    )
