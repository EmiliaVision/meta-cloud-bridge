from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from .types import MetaAccount, MetaChannel


@dataclass(slots=True)
class MetaBridgeConfig:
    graph_base_url: str = "https://graph.facebook.com"
    instagram_base_url: str = "https://graph.instagram.com"
    graph_version: str = "v25.0"
    app_id: str | None = None
    app_secret: str | None = None
    instagram_app_secret: str | None = None
    webhook_path: str = "/cloud"
    verify_token: str | None = None
    require_webhook_signature: bool = True
    accounts: list[MetaAccount] = field(default_factory=list)

    def by_key(self) -> dict[str, MetaAccount]:
        return {account.account_key: account for account in self.accounts}

    def by_webhook_asset(self) -> dict[str, list[MetaAccount]]:
        result: dict[str, list[MetaAccount]] = {}
        for account in self.accounts:
            for asset_id in account.webhook_asset_ids:
                result.setdefault(asset_id, []).append(account)
        return result

    def account_for_key(self, key: str | None) -> MetaAccount | None:
        if not key:
            return None
        for account in self.accounts:
            if key == account.account_key or key in account.webhook_asset_ids:
                return account
        return None

    def accounts_for_asset(
        self, asset_id: str | None, *, channel: MetaChannel | None = None
    ) -> list[MetaAccount]:
        if not asset_id:
            return []
        accounts = self.by_webhook_asset().get(asset_id, [])
        if channel:
            accounts = [account for account in accounts if account.channel is channel]
        return accounts


def _get(config: Any, key: str, default: Any = None) -> Any:
    try:
        value = config[key]
    except Exception:
        return default
    return default if value is None else value


def _get_dict(config: Any, key: str) -> dict[str, Any]:
    value = _get(config, key, {})
    return value if isinstance(value, dict) else {}


def _get_accounts(
    raw_accounts: Iterable[dict[str, Any]], bridge_config: MetaBridgeConfig
) -> list[MetaAccount]:
    accounts = []
    for raw_account in raw_accounts or []:
        if not raw_account:
            continue
        accounts.append(
            MetaAccount.from_config(
                raw_account,
                default_graph_base_url=bridge_config.graph_base_url,
                default_instagram_base_url=bridge_config.instagram_base_url,
                default_graph_version=bridge_config.graph_version,
            )
        )
    return accounts


def load_meta_config(config: Any) -> MetaBridgeConfig:
    raw_meta = _get_dict(config, "meta")
    legacy_whatsapp = _get_dict(config, "whatsapp")

    bridge_config = MetaBridgeConfig(
        graph_base_url=str(
            raw_meta.get("graph_base_url")
            or raw_meta.get("base_url")
            or legacy_whatsapp.get("base_url")
            or "https://graph.facebook.com"
        ).rstrip("/"),
        instagram_base_url=str(
            raw_meta.get("instagram_base_url") or "https://graph.instagram.com"
        ).rstrip("/"),
        graph_version=str(
            raw_meta.get("version")
            or raw_meta.get("graph_version")
            or legacy_whatsapp.get("version")
            or "v25.0"
        ),
        app_id=raw_meta.get("app_id"),
        app_secret=raw_meta.get("app_secret"),
        instagram_app_secret=raw_meta.get("instagram_app_secret"),
        webhook_path=str(
            raw_meta.get("webhook_path") or legacy_whatsapp.get("webhook_path") or "/cloud"
        ),
        verify_token=raw_meta.get("verify_token")
        or _get(config, "bridge.provisioning.shared_secret"),
        require_webhook_signature=bool(raw_meta.get("require_webhook_signature", True)),
    )
    bridge_config.accounts = _get_accounts(raw_meta.get("accounts") or [], bridge_config)
    return bridge_config
