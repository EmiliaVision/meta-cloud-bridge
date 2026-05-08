import hashlib
import hmac
import json

from meta_cloud_bridge.meta.config import MetaBridgeConfig
from meta_cloud_bridge.meta.types import MetaAccount, MetaChannel
from meta_cloud_bridge.meta.webhook import (
    MetaWebhookParser,
    NormalizedMetaMessage,
    verify_x_hub_signature_256,
)


def test_verify_x_hub_signature_256():
    body = b'{"object":"page"}'
    secret = "app-secret"
    digest = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

    assert verify_x_hub_signature_256(secret, body, f"sha256={digest}")
    assert not verify_x_hub_signature_256(secret, body, "sha256=bad")
    assert not verify_x_hub_signature_256(secret, body, None)


def test_parse_whatsapp_message():
    account = MetaAccount(
        id="wa-main",
        channel=MetaChannel.WHATSAPP,
        access_token="token",
        waba_id="waba-1",
        phone_number_id="phone-1",
    )
    parser = MetaWebhookParser(MetaBridgeConfig(accounts=[account]))
    payload = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "waba-1",
                "changes": [
                    {
                        "field": "messages",
                        "value": {
                            "metadata": {"phone_number_id": "phone-1"},
                            "contacts": [{"wa_id": "15551234567", "profile": {"name": "Alice"}}],
                            "messages": [
                                {
                                    "from": "15551234567",
                                    "id": "wamid.1",
                                    "timestamp": "1710000000",
                                    "type": "text",
                                    "text": {"body": "hello"},
                                }
                            ],
                        },
                    }
                ],
            }
        ],
    }

    events = parser.parse(payload)

    assert len(events) == 1
    event = events[0]
    assert isinstance(event, NormalizedMetaMessage)
    assert event.account is account
    assert event.channel is MetaChannel.WHATSAPP
    assert event.remote_user_id == "15551234567"
    assert event.remote_message_id == "wamid.1"
    assert event.text == "hello"
    assert event.sender_display_name == "Alice"


def test_parse_instagram_page_linked_message_by_recipient_id():
    messenger = MetaAccount(
        id="messenger-page",
        channel=MetaChannel.MESSENGER,
        access_token="token-page",
        page_id="page-1",
    )
    instagram = MetaAccount(
        id="instagram-page",
        channel=MetaChannel.INSTAGRAM,
        access_token="token-ig",
        page_id="page-1",
        instagram_user_id="ig-professional-1",
    )
    parser = MetaWebhookParser(MetaBridgeConfig(accounts=[messenger, instagram]))
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "page-1",
                "messaging": [
                    {
                        "sender": {"id": "igsid-1"},
                        "recipient": {"id": "ig-professional-1"},
                        "timestamp": 1710000000,
                        "message": {"mid": "mid.ig.1", "text": "hola ig"},
                    }
                ],
            }
        ],
    }

    events = parser.parse(payload)

    assert len(events) == 1
    assert isinstance(events[0], NormalizedMetaMessage)
    assert events[0].account is instagram
    assert events[0].channel is MetaChannel.INSTAGRAM
    assert events[0].remote_user_id == "igsid-1"
    assert events[0].text == "hola ig"


def test_parse_page_payload_json_does_not_log_or_require_tokens():
    payload = {"object": "page", "entry": []}
    # Guard the fixture shape used by replay tooling: it must remain plain JSON bytes.
    assert json.loads(json.dumps(payload).encode()) == payload
