from mautrix.types import MessageType

from meta_cloud_bridge.meta.channels import InstagramAdapter, MessengerAdapter, WhatsAppAdapter
from meta_cloud_bridge.meta.types import MetaAccount, MetaChannel


class FakeGraph:
    def __init__(self):
        self.calls = []

    async def send_message(self, account, payload):
        self.calls.append((account, payload))
        return {"message_id": "mid.fake"}

    async def mark_whatsapp_read(self, account, message_id):
        self.calls.append((account, {"status": "read", "message_id": message_id}))
        return {"success": True}


async def test_whatsapp_adapter_text_payload():
    account = MetaAccount(
        id="wa",
        channel=MetaChannel.WHATSAPP,
        access_token="token",
        phone_number_id="phone-1",
    )
    graph = FakeGraph()
    adapter = WhatsAppAdapter(account, graph)

    response = await adapter.send_text("15551234567", "hello", reply_to="wamid.old")

    assert response["message_id"] == "mid.fake"
    _, payload = graph.calls[0]
    assert payload == {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": "15551234567",
        "type": "text",
        "text": {"preview_url": False, "body": "hello"},
        "context": {"message_id": "wamid.old"},
    }


async def test_whatsapp_adapter_media_payload():
    account = MetaAccount(id="wa", channel=MetaChannel.WHATSAPP, access_token="token")
    graph = FakeGraph()
    adapter = WhatsAppAdapter(account, graph)

    await adapter.send_media(
        "15551234567",
        MessageType.FILE,
        "media-id",
        caption="caption",
        file_name="file.pdf",
    )

    _, payload = graph.calls[0]
    assert payload["type"] == "document"
    assert payload["document"] == {"id": "media-id", "filename": "file.pdf", "caption": "caption"}


async def test_messenger_adapter_text_payload():
    account = MetaAccount(
        id="page",
        channel=MetaChannel.MESSENGER,
        access_token="token",
        page_id="page-1",
    )
    graph = FakeGraph()
    adapter = MessengerAdapter(account, graph)

    await adapter.send_text("psid-1", "hello")

    _, payload = graph.calls[0]
    assert payload == {
        "recipient": {"id": "psid-1"},
        "messaging_type": "RESPONSE",
        "message": {"text": "hello"},
    }


async def test_instagram_adapter_text_payload():
    account = MetaAccount(
        id="ig",
        channel=MetaChannel.INSTAGRAM,
        access_token="token",
        page_id="page-1",
        instagram_user_id="ig-1",
    )
    graph = FakeGraph()
    adapter = InstagramAdapter(account, graph)

    await adapter.send_text("igsid-1", "hello")

    _, payload = graph.calls[0]
    assert payload == {
        "recipient": {"id": "igsid-1"},
        "message": {"text": "hello"},
    }
