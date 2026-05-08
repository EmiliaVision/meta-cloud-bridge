from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from mautrix.types import UserID


class MetaChannel(StrEnum):
    WHATSAPP = "whatsapp"
    MESSENGER = "messenger"
    INSTAGRAM = "instagram"
    INSTAGRAM_LOGIN = "instagram_login"

    @property
    def graph_host(self) -> str:
        return (
            "graph.instagram.com" if self is MetaChannel.INSTAGRAM_LOGIN else "graph.facebook.com"
        )

    @property
    def display_name(self) -> str:
        return {
            MetaChannel.WHATSAPP: "WhatsApp",
            MetaChannel.MESSENGER: "Messenger",
            MetaChannel.INSTAGRAM: "Instagram",
            MetaChannel.INSTAGRAM_LOGIN: "Instagram Login",
        }[self]


@dataclass(slots=True)
class MetaAccount:
    id: str
    channel: MetaChannel
    access_token: str
    owner_mxid: UserID | None = None
    invite_mxids: list[UserID] = field(default_factory=list)
    graph_base_url: str = "https://graph.facebook.com"
    graph_version: str = "v25.0"
    waba_id: str | None = None
    phone_number_id: str | None = None
    page_id: str | None = None
    instagram_user_id: str | None = None
    label: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def account_key(self) -> str:
        """Stable internal account key stored in portal/message/account_id columns."""
        return self.id or f"{self.channel}:{self.asset_id}"

    @property
    def asset_id(self) -> str:
        if self.channel is MetaChannel.WHATSAPP:
            return self.waba_id or self.phone_number_id or self.id
        if self.channel in (MetaChannel.MESSENGER, MetaChannel.INSTAGRAM):
            return self.page_id or self.id
        if self.channel is MetaChannel.INSTAGRAM_LOGIN:
            return self.instagram_user_id or self.id
        return self.id

    @property
    def send_asset_id(self) -> str:
        if self.channel is MetaChannel.WHATSAPP:
            return self.phone_number_id or self.asset_id
        if self.channel in (MetaChannel.MESSENGER, MetaChannel.INSTAGRAM):
            return self.page_id or self.asset_id
        if self.channel is MetaChannel.INSTAGRAM_LOGIN:
            return self.instagram_user_id or self.asset_id
        return self.asset_id

    @property
    def webhook_asset_ids(self) -> set[str]:
        ids = {self.id, self.account_key, self.asset_id, self.send_asset_id}
        for value in (self.waba_id, self.phone_number_id, self.page_id, self.instagram_user_id):
            if value:
                ids.add(value)
        return {value for value in ids if value}

    @property
    def legacy_business_id(self) -> str:
        """Deprecated compatibility alias for old WhatsApp-only code paths."""
        if self.channel is MetaChannel.WHATSAPP:
            return self.waba_id or self.asset_id
        return self.account_key

    @property
    def legacy_phone_id(self) -> str | None:
        """Deprecated compatibility alias for old WhatsApp-only code paths."""
        return self.send_asset_id

    @property
    def room_topic(self) -> str:
        return f"{self.channel.display_name} private chat"

    @classmethod
    def from_config(
        cls,
        data: dict[str, Any],
        *,
        default_graph_base_url: str,
        default_instagram_base_url: str,
        default_graph_version: str,
    ) -> MetaAccount:
        channel = MetaChannel(data["channel"])
        graph_base_url = data.get("graph_base_url")
        if not graph_base_url:
            graph_base_url = (
                default_instagram_base_url
                if channel is MetaChannel.INSTAGRAM_LOGIN
                else default_graph_base_url
            )

        account_id = data.get("id")
        if not account_id:
            account_id = (
                data.get("waba_id")
                or data.get("page_id")
                or data.get("instagram_user_id")
                or data.get("phone_number_id")
            )
        if not account_id:
            raise ValueError("Meta account is missing id/asset identifier")

        token = data.get("access_token")
        if not token:
            raise ValueError(f"Meta account {account_id} is missing access_token")

        owner_mxid = data.get("owner_mxid") or data.get("admin_mxid")
        invite_mxids = data.get("invite_mxids") or []
        if owner_mxid and owner_mxid not in invite_mxids:
            invite_mxids = [owner_mxid, *invite_mxids]

        return cls(
            id=str(account_id),
            channel=channel,
            access_token=str(token),
            owner_mxid=UserID(owner_mxid) if owner_mxid else None,
            invite_mxids=[UserID(mxid) for mxid in invite_mxids],
            graph_base_url=str(graph_base_url).rstrip("/"),
            graph_version=str(
                data.get("version") or data.get("graph_version") or default_graph_version
            ),
            waba_id=str(data["waba_id"]) if data.get("waba_id") else None,
            phone_number_id=str(data["phone_number_id"]) if data.get("phone_number_id") else None,
            page_id=str(data["page_id"]) if data.get("page_id") else None,
            instagram_user_id=(
                str(data["instagram_user_id"]) if data.get("instagram_user_id") else None
            ),
            label=data.get("label") or data.get("name"),
            extra={key: value for key, value in data.items() if key not in _KNOWN_ACCOUNT_KEYS},
        )


_KNOWN_ACCOUNT_KEYS = {
    "id",
    "channel",
    "access_token",
    "owner_mxid",
    "admin_mxid",
    "invite_mxids",
    "graph_base_url",
    "version",
    "graph_version",
    "waba_id",
    "phone_number_id",
    "page_id",
    "instagram_user_id",
    "label",
    "name",
}
