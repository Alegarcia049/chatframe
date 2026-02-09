from app2.api.v1.meta_webhook import (
    parse_instagram,
    parse_messenger,
    parse_meta_payload,
    parse_meta_payload_detailed,
    parse_whatsapp,
)


def test_parse_whatsapp_text_message():
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "WABA1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "messaging_product": "whatsapp",
                            "messages": [
                                {
                                    "from": "549111",
                                    "id": "wamid.1",
                                    "timestamp": "1",
                                    "type": "text",
                                    "text": {"body": "hola"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    result = parse_whatsapp(payload)
    assert len(result) == 1
    assert result[0]["platform"] == "wa"
    assert result[0]["message_id"] == "wamid.1"
    assert result[0]["text"] == "hola"


def test_parse_messenger_text_message_fb():
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE1",
                "messaging": [
                    {
                        "sender": {"id": "user_1"},
                        "recipient": {"id": "page_1"},
                        "timestamp": 1700,
                        "message": {"mid": "mid.1", "text": "hola fb"},
                    }
                ],
            }
        ],
    }

    result = parse_messenger(payload)
    assert len(result) == 1
    assert result[0]["platform"] == "fb"
    assert result[0]["message_id"] == "mid.1"


def test_parse_instagram_text_message_ig():
    payload = {
        "object": "instagram",
        "entry": [
            {
                "id": "IG1",
                "messaging": [
                    {
                        "sender": {"id": "ig_user_1"},
                        "recipient": {"id": "ig_page_1"},
                        "timestamp": 1701,
                        "message": {"mid": "igmid.1", "text": "hola ig"},
                    }
                ],
            }
        ],
    }

    result = parse_instagram(payload)
    assert len(result) == 1
    assert result[0]["platform"] == "ig"
    assert result[0]["message_id"] == "igmid.1"


def test_parse_meta_payload_ignores_non_text_events():
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "PAGE1",
                "messaging": [
                    {
                        "sender": {"id": "user_1"},
                        "recipient": {"id": "page_1"},
                        "timestamp": 1700,
                        "delivery": {"mids": ["mid.1"]},
                    }
                ],
            }
        ],
    }

    result = parse_meta_payload(payload)
    detailed, ignored = parse_meta_payload_detailed(payload)
    assert result == []
    assert detailed == []
    assert len(ignored) == 1
    assert ignored[0]["reason"] == "non_message_event"
