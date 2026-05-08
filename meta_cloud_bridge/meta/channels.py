from __future__ import annotations

from typing import Any

from mautrix.types import MessageType

from .client import MetaGraphClient
from .types import MetaAccount, MetaChannel


class UnsupportedMetaMessageError(TypeError):
    pass


class BaseChannelAdapter:
    def __init__(self, account: MetaAccount, graph: MetaGraphClient) -> None:
        self.account = account
        self.graph = graph

    async def send_text(
        self,
        remote_user_id: str,
        text: str,
        *,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError

    async def send_media(
        self,
        remote_user_id: str,
        message_type: MessageType,
        media_id_or_url: str,
        *,
        caption: str | None = None,
        file_name: str | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        raise UnsupportedMetaMessageError(
            f"{self.account.channel} media sending is not implemented"
        )

    async def send_location(
        self,
        remote_user_id: str,
        latitude: str,
        longitude: str,
        *,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        raise UnsupportedMetaMessageError(
            f"{self.account.channel} location sending is not implemented"
        )

    async def send_reaction(
        self,
        remote_user_id: str,
        message_id: str,
        emoji: str,
    ) -> dict[str, Any]:
        raise UnsupportedMetaMessageError(
            f"{self.account.channel} reaction sending is not implemented"
        )

    async def mark_read(self, message_id: str) -> dict[str, Any]:
        return {}


class WhatsAppAdapter(BaseChannelAdapter):
    async def send_text(
        self,
        remote_user_id: str,
        text: str,
        *,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": remote_user_id,
            "type": "text",
            "text": {"preview_url": False, "body": text},
        }
        if reply_to:
            payload["context"] = {"message_id": reply_to}
        return await self.graph.send_message(self.account, payload)

    async def send_media(
        self,
        remote_user_id: str,
        message_type: MessageType,
        media_id_or_url: str,
        *,
        caption: str | None = None,
        file_name: str | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        if message_type == MessageType.IMAGE:
            meta_type = "image"
            media_payload = {"id": media_id_or_url, "caption": caption}
        elif message_type == MessageType.VIDEO:
            meta_type = "video"
            media_payload = {"id": media_id_or_url, "caption": caption}
        elif message_type == MessageType.AUDIO:
            meta_type = "audio"
            media_payload = {"id": media_id_or_url}
        elif message_type == MessageType.FILE:
            meta_type = "document"
            media_payload = {"id": media_id_or_url, "filename": file_name, "caption": caption}
        else:
            raise UnsupportedMetaMessageError(f"Unsupported WhatsApp media type: {message_type}")

        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": remote_user_id,
            "type": meta_type,
            meta_type: {k: v for k, v in media_payload.items() if v is not None},
        }
        if reply_to:
            payload["context"] = {"message_id": reply_to}
        return await self.graph.send_message(self.account, payload)

    async def send_location(
        self,
        remote_user_id: str,
        latitude: str,
        longitude: str,
        *,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": remote_user_id,
            "type": "location",
            "location": {"latitude": latitude, "longitude": longitude},
        }
        if reply_to:
            payload["context"] = {"message_id": reply_to}
        return await self.graph.send_message(self.account, payload)

    async def send_reaction(
        self,
        remote_user_id: str,
        message_id: str,
        emoji: str,
    ) -> dict[str, Any]:
        return await self.graph.send_message(
            self.account,
            {
                "messaging_product": "whatsapp",
                "recipient_type": "individual",
                "to": remote_user_id,
                "type": "reaction",
                "reaction": {"message_id": message_id, "emoji": emoji},
            },
        )

    async def mark_read(self, message_id: str) -> dict[str, Any]:
        return await self.graph.mark_whatsapp_read(self.account, message_id)


class MessengerAdapter(BaseChannelAdapter):
    async def send_text(
        self,
        remote_user_id: str,
        text: str,
        *,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "recipient": {"id": remote_user_id},
            "messaging_type": "RESPONSE",
            "message": {"text": text},
        }
        if reply_to:
            payload["message"]["reply_to"] = {"mid": reply_to}
        return await self.graph.send_message(self.account, payload)

    async def send_media(
        self,
        remote_user_id: str,
        message_type: MessageType,
        media_id_or_url: str,
        *,
        caption: str | None = None,
        file_name: str | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        attachment_type = {
            MessageType.IMAGE: "image",
            MessageType.VIDEO: "video",
            MessageType.AUDIO: "audio",
            MessageType.FILE: "file",
        }.get(message_type)
        if not attachment_type:
            raise UnsupportedMetaMessageError(f"Unsupported Messenger media type: {message_type}")
        payload: dict[str, Any] = {
            "recipient": {"id": remote_user_id},
            "messaging_type": "RESPONSE",
            "message": {
                "attachment": {
                    "type": attachment_type,
                    "payload": {"url": media_id_or_url, "is_reusable": True},
                }
            },
        }
        if reply_to:
            payload["message"]["reply_to"] = {"mid": reply_to}
        return await self.graph.send_message(self.account, payload)


class InstagramAdapter(MessengerAdapter):
    async def send_text(
        self,
        remote_user_id: str,
        text: str,
        *,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "recipient": {"id": remote_user_id},
            "message": {"text": text},
        }
        if reply_to:
            payload["message"]["reply_to"] = {"mid": reply_to}
        return await self.graph.send_message(self.account, payload)


class InstagramLoginAdapter(InstagramAdapter):
    pass


def make_adapter(account: MetaAccount, graph: MetaGraphClient) -> BaseChannelAdapter:
    if account.channel is MetaChannel.WHATSAPP:
        return WhatsAppAdapter(account, graph)
    if account.channel is MetaChannel.MESSENGER:
        return MessengerAdapter(account, graph)
    if account.channel is MetaChannel.INSTAGRAM:
        return InstagramAdapter(account, graph)
    if account.channel is MetaChannel.INSTAGRAM_LOGIN:
        return InstagramLoginAdapter(account, graph)
    raise UnsupportedMetaMessageError(f"Unsupported Meta channel: {account.channel}")
