from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Iterable

from aiohttp import web
from mautrix.types import UserID

from meta_cloud_bridge.db import MetaAccountRecord as DBMetaAccount
from meta_cloud_bridge.portal import Portal
from meta_cloud_bridge.user import User
from whatsapp.data import WhatsappContacts, WhatsappEvent

from .config import MetaBridgeConfig
from .types import MetaAccount, MetaChannel


@dataclass(slots=True)
class NormalizedMetaMessage:
    channel: MetaChannel
    account: MetaAccount
    asset_id: str
    remote_user_id: str
    remote_message_id: str
    text: str | None = None
    timestamp: int | None = None
    sender_display_name: str | None = None
    message_type: str = "text"
    attachments: list[dict[str, Any]] = field(default_factory=list)
    reply_to: str | None = None
    is_echo: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        return f"message:{self.channel}:{self.account.account_key}:{self.remote_message_id}"


@dataclass(slots=True)
class NormalizedMetaStatus:
    channel: MetaChannel
    account: MetaAccount
    remote_user_id: str | None
    remote_message_id: str
    status: str
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        return f"status:{self.channel}:{self.account.account_key}:{self.remote_message_id}:{self.status}"


@dataclass(slots=True)
class NormalizedMetaReaction:
    channel: MetaChannel
    account: MetaAccount
    remote_user_id: str
    remote_message_id: str
    target_message_id: str
    emoji: str | None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def dedup_key(self) -> str:
        return f"reaction:{self.channel}:{self.account.account_key}:{self.remote_message_id}:{self.emoji or ''}"


NormalizedMetaEvent = NormalizedMetaMessage | NormalizedMetaStatus | NormalizedMetaReaction


class WebhookDeduplicator:
    def __init__(self, max_size: int = 10000) -> None:
        self.max_size = max_size
        self._seen: OrderedDict[str, None] = OrderedDict()

    def seen(self, key: str) -> bool:
        if key in self._seen:
            self._seen.move_to_end(key)
            return True
        self._seen[key] = None
        if len(self._seen) > self.max_size:
            self._seen.popitem(last=False)
        return False


def verify_x_hub_signature_256(app_secret: str, raw_body: bytes, header: str | None) -> bool:
    if not app_secret or not header:
        return False
    if not header.startswith("sha256="):
        return False
    expected = hmac.new(app_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    received = header.removeprefix("sha256=")
    return hmac.compare_digest(expected, received)


class MetaWebhookParser:
    log = logging.getLogger("meta.webhook.parser")

    def __init__(self, config: MetaBridgeConfig) -> None:
        self.config = config

    def parse(self, payload: dict[str, Any]) -> list[NormalizedMetaEvent]:
        object_type = payload.get("object")
        if object_type == "whatsapp_business_account":
            return list(self._parse_whatsapp(payload))
        if object_type == "page":
            return list(self._parse_page(payload))
        if object_type == "instagram":
            return list(self._parse_instagram_login(payload))
        self.log.debug("Ignoring unsupported Meta webhook object %s", object_type)
        return []

    def _account_for_whatsapp(
        self, entry: dict[str, Any], value: dict[str, Any]
    ) -> MetaAccount | None:
        waba_id = entry.get("id")
        phone_number_id = (value.get("metadata") or {}).get("phone_number_id")
        # Prefer the most specific match: phone_number_id first, then waba_id.
        # Multiple accounts can share the same WABA (e.g. two phone numbers under
        # one WhatsApp Business Account), so matching by phone_number_id avoids
        # always returning the first configured account.
        if phone_number_id:
            by_phone = self.config.accounts_for_asset(
                phone_number_id, channel=MetaChannel.WHATSAPP
            )
            if by_phone:
                return by_phone[0]
        if waba_id:
            by_waba = self.config.accounts_for_asset(waba_id, channel=MetaChannel.WHATSAPP)
            if by_waba:
                return by_waba[0]
        if waba_id:
            # Compatibility path for WhatsApp accounts registered through the legacy
            # provisioning API rather than meta.accounts.
            return MetaAccount(
                id=waba_id,
                channel=MetaChannel.WHATSAPP,
                access_token="",
                graph_base_url=self.config.graph_base_url,
                graph_version=self.config.graph_version,
                waba_id=waba_id,
                phone_number_id=phone_number_id,
                extra={"legacy_fallback": True},
            )
        return None

    def _parse_whatsapp(self, payload: dict[str, Any]) -> Iterable[NormalizedMetaEvent]:
        for entry in payload.get("entry") or []:
            for change in entry.get("changes") or []:
                value = change.get("value") or {}
                account = self._account_for_whatsapp(entry, value)
                if not account:
                    self.log.warning(
                        "Ignoring WhatsApp webhook for unconfigured asset %s", entry.get("id")
                    )
                    continue

                contacts_by_wa_id = {
                    contact.get("wa_id"): contact for contact in value.get("contacts") or []
                }

                for message in value.get("messages") or []:
                    remote_user_id = message.get("from")
                    contact = contacts_by_wa_id.get(remote_user_id) or {}
                    profile = contact.get("profile") or {}
                    message_type = message.get("type") or "text"
                    if message_type == "reaction":
                        reaction = message.get("reaction") or {}
                        yield NormalizedMetaReaction(
                            channel=MetaChannel.WHATSAPP,
                            account=account,
                            remote_user_id=remote_user_id,
                            remote_message_id=message.get("id") or reaction.get("message_id"),
                            target_message_id=reaction.get("message_id"),
                            emoji=reaction.get("emoji"),
                            raw=message,
                        )
                        continue

                    text = (message.get("text") or {}).get("body")
                    attachments = []
                    for attachment_type in ("image", "video", "audio", "document", "sticker"):
                        if message.get(attachment_type):
                            attachments.append(
                                {"type": attachment_type, **message[attachment_type]}
                            )

                    context = message.get("context") or {}
                    yield NormalizedMetaMessage(
                        channel=MetaChannel.WHATSAPP,
                        account=account,
                        asset_id=entry.get("id") or account.asset_id,
                        remote_user_id=remote_user_id,
                        remote_message_id=message.get("id"),
                        text=text,
                        timestamp=_safe_int(message.get("timestamp")),
                        sender_display_name=profile.get("name"),
                        message_type=message_type,
                        attachments=attachments,
                        reply_to=context.get("id"),
                        raw=message,
                    )

                for status in value.get("statuses") or []:
                    yield NormalizedMetaStatus(
                        channel=MetaChannel.WHATSAPP,
                        account=account,
                        remote_user_id=status.get("recipient_id"),
                        remote_message_id=status.get("id"),
                        status=status.get("status"),
                        raw=status,
                    )

    def _account_for_page_event(
        self, entry: dict[str, Any], event: dict[str, Any]
    ) -> MetaAccount | None:
        recipient_id = (event.get("recipient") or {}).get("id")
        page_id = entry.get("id") or recipient_id
        accounts = []
        for asset_id in (page_id, recipient_id):
            for account in self.config.accounts_for_asset(asset_id):
                if account not in accounts:
                    accounts.append(account)
        if not accounts:
            return None

        recipient_accounts = self.config.accounts_for_asset(recipient_id)
        if len(recipient_accounts) == 1:
            return recipient_accounts[0]

        if len(accounts) == 1:
            return accounts[0]

        # If Messenger and Instagram share a Page, allow dashboard payload hints to break ties.
        event_product = event.get("messaging_product") or event.get("platform")
        if event_product == "instagram":
            for account in accounts:
                if account.channel is MetaChannel.INSTAGRAM:
                    return account
        if event_product == "messenger":
            for account in accounts:
                if account.channel is MetaChannel.MESSENGER:
                    return account

        # Default to Messenger for page events unless the Page is configured only for Instagram.
        for account in accounts:
            if account.channel is MetaChannel.MESSENGER:
                return account
        return accounts[0]

    def _parse_page(self, payload: dict[str, Any]) -> Iterable[NormalizedMetaEvent]:
        for entry in payload.get("entry") or []:
            for event in entry.get("messaging") or []:
                account = self._account_for_page_event(entry, event)
                if not account:
                    self.log.warning(
                        "Ignoring Page webhook for unconfigured Page %s", entry.get("id")
                    )
                    continue

                sender_id = (event.get("sender") or {}).get("id")
                recipient_id = (event.get("recipient") or {}).get("id")
                message = event.get("message") or {}
                if not message:
                    continue

                is_echo = bool(message.get("is_echo"))
                if is_echo:
                    remote_user_id = (
                        recipient_id if recipient_id != account.asset_id else sender_id
                    )
                else:
                    remote_user_id = sender_id

                if message.get("reaction"):
                    reaction = message.get("reaction") or {}
                    yield NormalizedMetaReaction(
                        channel=account.channel,
                        account=account,
                        remote_user_id=remote_user_id,
                        remote_message_id=message.get("mid") or event.get("timestamp"),
                        target_message_id=reaction.get("mid") or reaction.get("message_id"),
                        emoji=reaction.get("emoji") or reaction.get("reaction"),
                        raw=event,
                    )
                    continue

                yield NormalizedMetaMessage(
                    channel=account.channel,
                    account=account,
                    asset_id=entry.get("id") or account.asset_id,
                    remote_user_id=remote_user_id,
                    remote_message_id=message.get("mid"),
                    text=message.get("text"),
                    timestamp=_safe_int(event.get("timestamp")),
                    message_type="attachments" if message.get("attachments") else "text",
                    attachments=message.get("attachments") or [],
                    reply_to=(message.get("reply_to") or {}).get("mid"),
                    is_echo=is_echo,
                    raw=event,
                )

    def _parse_instagram_login(self, payload: dict[str, Any]) -> Iterable[NormalizedMetaEvent]:
        for entry in payload.get("entry") or []:
            # Try Instagram Login accounts first, then fall back to Page-linked Instagram.
            # Webhooks for both arrive as object="instagram".
            accounts = self.config.accounts_for_asset(
                entry.get("id"), channel=MetaChannel.INSTAGRAM_LOGIN
            )
            if not accounts:
                accounts = self.config.accounts_for_asset(
                    entry.get("id"), channel=MetaChannel.INSTAGRAM
                )
            if not accounts:
                self.log.warning(
                    "Ignoring Instagram webhook for unconfigured account %s", entry.get("id")
                )
                continue
            account = accounts[0]
            for event in entry.get("messaging") or []:
                message = event.get("message") or {}
                if not message:
                    continue
                sender_id = (event.get("sender") or {}).get("id")
                recipient_id = (event.get("recipient") or {}).get("id")
                is_echo = bool(message.get("is_echo"))
                remote_user_id = sender_id if sender_id != account.asset_id else recipient_id
                if is_echo:
                    remote_user_id = (
                        recipient_id if recipient_id != account.asset_id else sender_id
                    )
                yield NormalizedMetaMessage(
                    channel=account.channel,
                    account=account,
                    asset_id=entry.get("id") or account.asset_id,
                    remote_user_id=remote_user_id,
                    remote_message_id=message.get("mid"),
                    text=message.get("text"),
                    timestamp=_safe_int(event.get("timestamp")),
                    message_type="attachments" if message.get("attachments") else "text",
                    attachments=message.get("attachments") or [],
                    reply_to=(message.get("reply_to") or {}).get("mid"),
                    is_echo=is_echo,
                    raw=event,
                )


class MetaHandler:
    log = logging.getLogger("meta.webhook")

    def __init__(self, *, config: MetaBridgeConfig, loop=None) -> None:
        self.config = config
        self.parser = MetaWebhookParser(config)
        self.dedup = WebhookDeduplicator()
        self.app = web.Application(loop=loop)
        self.app.router.add_route("GET", "/receive", self.verify_connection)
        self.app.router.add_route("POST", "/receive", self.receive)

    async def verify_connection(self, request: web.Request) -> web.Response:
        mode = request.query.get("hub.mode")
        token = request.query.get("hub.verify_token")
        challenge = request.query.get("hub.challenge")
        if mode == "subscribe" and token == self.config.verify_token and challenge is not None:
            self.log.info("Meta webhook verified")
            return web.Response(text=challenge, status=200)
        raise web.HTTPForbidden(
            text=json.dumps({"detail": {"message": "The verify token is invalid."}}),
            content_type="application/json",
        )

    async def receive(self, request: web.Request) -> web.Response:
        raw_body = await request.read()
        if self.config.require_webhook_signature:
            if not self.config.app_secret:
                self.log.error(
                    "Webhook signature validation is required but meta.app_secret is empty"
                )
                raise web.HTTPForbidden(text="signature validation is not configured")
            signature = request.headers.get("X-Hub-Signature-256")
            # Try the primary app_secret first, then instagram_app_secret.
            # Instagram webhooks are signed with a separate app secret.
            valid = verify_x_hub_signature_256(self.config.app_secret, raw_body, signature)
            if not valid and self.config.instagram_app_secret:
                valid = verify_x_hub_signature_256(
                    self.config.instagram_app_secret, raw_body, signature
                )
            if not valid:
                self.log.warning("Rejecting Meta webhook with invalid signature")
                raise web.HTTPForbidden(text="invalid signature")

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except json.JSONDecodeError:
            raise web.HTTPBadRequest(text="invalid json")

        self.log.debug("Received Meta webhook object=%s", payload.get("object"))
        for event in self.parser.parse(payload):
            if self.dedup.seen(event.dedup_key):
                self.log.debug("Ignoring duplicate Meta webhook event %s", event.dedup_key)
                continue
            asyncio.create_task(self._dispatch_event_safely(event, payload))
        return web.Response(status=200)

    async def _dispatch_event_safely(
        self, event: NormalizedMetaEvent, payload: dict[str, Any]
    ) -> None:
        try:
            await self.dispatch_event(event, payload)
        except Exception:
            self.log.exception("Error dispatching Meta webhook event %s", event.dedup_key)

    async def dispatch_event(self, event: NormalizedMetaEvent, payload: dict[str, Any]) -> None:
        if isinstance(event, NormalizedMetaMessage):
            if event.channel is MetaChannel.WHATSAPP:
                await self._dispatch_whatsapp_message(event, payload)
            else:
                await self._dispatch_generic_message(event)
        elif isinstance(event, NormalizedMetaStatus):
            await self._dispatch_status(event)
        elif isinstance(event, NormalizedMetaReaction):
            await self._dispatch_reaction(event)

    async def _source_user_for_account(self, account: MetaAccount) -> User | None:
        if account.owner_mxid:
            return await User.get_by_mxid(UserID(account.owner_mxid), create=True)
        return await User.get_by_account_id(account.account_key) or await User.get_by_account_id(
            account.asset_id
        )

    async def _ensure_meta_account(self, account: MetaAccount) -> bool:
        if await DBMetaAccount.get_by_account_id(account.account_key):
            return True
        if account.extra.get("legacy_fallback"):
            return False
        admin_user = str(account.owner_mxid or "@meta-cloud-bridge:localhost")
        await DBMetaAccount.insert(
            name=account.label or account.id,
            admin_user=admin_user,
            account_id=account.account_key,
            channel=account.channel.value,
            asset_id=account.asset_id,
            send_asset_id=account.send_asset_id,
            access_token=account.access_token,
        )
        return True

    async def _dispatch_whatsapp_message(
        self, event: NormalizedMetaMessage, payload: dict[str, Any]
    ) -> None:
        if not await self._ensure_meta_account(event.account):
            self.log.warning(
                "Ignoring WhatsApp webhook for unregistered WABA %s", event.account.id
            )
            return
        source = await self._source_user_for_account(event.account)
        if not source:
            self.log.warning(
                "No Matrix owner configured for WhatsApp account %s", event.account.id
            )
            return

        whatsapp_event = WhatsappEvent.from_dict(payload)
        sender = whatsapp_event.entry.changes.value.contacts
        portal = await Portal.get_by_app_and_phone_id(
            phone_id=event.remote_user_id,
            app_business_id=event.account.account_key,
        )
        if whatsapp_event.entry.changes.value.messages.errors:
            await portal.handle_whatsapp_errors(whatsapp_event.entry.changes.value.messages.errors)
        elif whatsapp_event.entry.changes.value.messages.type == "reaction":
            await portal.handle_whatsapp_reaction(whatsapp_event, sender.wa_id)
        elif whatsapp_event.entry.changes.value.messages.type == "edit":
            await portal.handle_whatsapp_edit(
                sender_id=sender.wa_id,
                message_to_edit=whatsapp_event.entry.changes.value.messages,
                intent=portal.main_intent,
            )
        else:
            await portal.handle_whatsapp_message(source, whatsapp_event, sender)

    async def _dispatch_generic_message(self, event: NormalizedMetaMessage) -> None:
        if not await self._ensure_meta_account(event.account):
            self.log.warning("Ignoring Meta webhook for unregistered account %s", event.account.id)
            return
        source = await self._source_user_for_account(event.account)
        if not source:
            self.log.warning("No Matrix owner configured for Meta account %s", event.account.id)
            return
        portal = await Portal.get_by_app_and_phone_id(
            phone_id=event.remote_user_id,
            app_business_id=event.account.account_key,
        )
        await portal.handle_meta_message(source, event)

    async def _dispatch_status(self, event: NormalizedMetaStatus) -> None:
        if event.status == "read" and event.remote_user_id:
            portal = await Portal.get_by_app_and_phone_id(
                phone_id=event.remote_user_id,
                app_business_id=event.account.account_key,
                create=False,
            )
            if portal:
                await portal.handle_whatsapp_read(event.remote_message_id)

        if event.status == "failed" and event.remote_user_id:
            portal = await Portal.get_by_app_and_phone_id(
                phone_id=event.remote_user_id,
                app_business_id=event.account.account_key,
                create=False,
            )
            if portal:
                errors = event.raw.get("errors") or []
                details = (
                    errors[0].get("error_data", {}).get("details")
                    if errors
                    else "Meta send failed"
                )
                await portal.handle_whatsapp_error(details)

    async def _dispatch_reaction(self, event: NormalizedMetaReaction) -> None:
        if event.channel is MetaChannel.WHATSAPP:
            # WhatsApp reaction payloads are handled by the native WhatsApp parser above.
            return
        portal = await Portal.get_by_app_and_phone_id(
            phone_id=event.remote_user_id,
            app_business_id=event.account.account_key,
            create=False,
        )
        if portal:
            await portal.handle_meta_reaction(event)


def make_contact(remote_user_id: str, display_name: str | None = None) -> WhatsappContacts:
    data: dict[str, Any] = {"wa_id": remote_user_id}
    if display_name:
        data["profile"] = {"name": display_name}
    return WhatsappContacts.deserialize(data)


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except TypeError, ValueError:
        return None
