from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar, List, Optional

import asyncpg
from attr import dataclass
from mautrix.types import UserID
from mautrix.util.async_db import Database

from whatsapp.data import WsBusinessID, WSPhoneID

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class MetaAccountRecord:
    db: ClassVar[Database] = fake_db

    account_id: str | None
    channel: str
    asset_id: str | None
    send_asset_id: str | None
    name: str
    admin_user: UserID
    access_token: str | None

    @property
    def business_id(self) -> WsBusinessID | None:
        """Compatibility alias for WhatsApp template-management code.

        For WhatsApp this is the WABA ID (`asset_id`). For other channels this
        falls back to the internal `account_id`.
        """
        return self.asset_id or self.account_id

    @property
    def wb_phone_id(self) -> WSPhoneID | None:
        """Compatibility alias for WhatsApp send endpoint asset ID."""
        return self.send_asset_id or self.asset_id

    @property
    def page_access_token(self) -> str | None:
        """Compatibility alias for older WhatsApp provisioning code."""
        return self.access_token

    @property
    def _values(self):
        return (
            self.account_id,
            self.channel,
            self.asset_id,
            self.send_asset_id,
            self.name,
            self.admin_user,
            self.access_token,
        )

    _columns = "account_id, channel, asset_id, send_asset_id, name, admin_user, access_token"

    @classmethod
    def _from_row(cls, row: asyncpg.Record) -> MetaAccountRecord:
        return cls(**row)

    @classmethod
    async def insert(
        cls,
        name: str,
        admin_user: str,
        account_id: str | None = None,
        asset_id: str | None = None,
        send_asset_id: str | None = None,
        access_token: str | None = None,
        channel: str = "whatsapp",
        *,
        business_id: WsBusinessID | None = None,
        wb_phone_id: WSPhoneID | None = None,
        page_access_token: str | None = None,
    ) -> None:
        account_id = account_id or business_id
        asset_id = asset_id or business_id or account_id
        send_asset_id = send_asset_id or wb_phone_id or asset_id
        access_token = access_token or page_access_token
        q = f"INSERT INTO meta_account ({cls._columns}) VALUES ($1, $2, $3, $4, $5, $6, $7)"
        await cls.db.execute(
            q, account_id, channel, asset_id, send_asset_id, name, admin_user, access_token
        )

    @classmethod
    async def update(
        cls,
        name: str,
        admin_user: str,
        account_id: str | None = None,
        asset_id: str | None = None,
        send_asset_id: str | None = None,
        access_token: str | None = None,
        channel: str = "whatsapp",
        *,
        business_id: WsBusinessID | None = None,
        wb_phone_id: WSPhoneID | None = None,
        page_access_token: str | None = None,
    ) -> None:
        account_id = account_id or business_id
        asset_id = asset_id or business_id or account_id
        send_asset_id = send_asset_id or wb_phone_id or asset_id
        access_token = access_token or page_access_token
        q = """
            UPDATE meta_account
            SET channel=$2, asset_id=$3, send_asset_id=$4, name=$5, admin_user=$6, access_token=$7
            WHERE account_id=$1
        """
        await cls.db.execute(
            q, account_id, channel, asset_id, send_asset_id, name, admin_user, access_token
        )

    @classmethod
    async def update_by_admin_user(cls, user: str, values: tuple[str, str | None]) -> None:
        """Update the account display name and access token for an admin user."""
        q = """
            UPDATE meta_account
            SET name=$2, access_token=$3
            WHERE admin_user=$1
        """
        await cls.db.execute(q, user, *values)

    @classmethod
    async def get_by_name(cls, name: str) -> Optional["MetaAccountRecord"]:
        q = f"SELECT {cls._columns} FROM meta_account WHERE name=$1"
        row = await cls.db.fetchrow(q, name)

        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def get_by_account_id(cls, account_id: str) -> Optional["MetaAccountRecord"]:
        q = f"SELECT {cls._columns} FROM meta_account WHERE account_id=$1"
        row = await cls.db.fetchrow(q, account_id)

        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def get_by_business_id(cls, business_id: WsBusinessID) -> Optional["MetaAccountRecord"]:
        q = f"SELECT {cls._columns} FROM meta_account WHERE account_id=$1 OR asset_id=$1"
        row = await cls.db.fetchrow(q, business_id)

        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def get_by_asset_id(cls, asset_id: str) -> Optional["MetaAccountRecord"]:
        q = f"SELECT {cls._columns} FROM meta_account WHERE asset_id=$1 OR send_asset_id=$1"
        row = await cls.db.fetchrow(q, asset_id)

        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def get_by_wb_phone_id(cls, wb_phone_id: WSPhoneID) -> Optional["MetaAccountRecord"]:
        return await cls.get_by_asset_id(wb_phone_id)

    @classmethod
    async def get_by_admin_user(cls, admin_user: UserID) -> Optional["MetaAccountRecord"]:
        q = f"SELECT {cls._columns} FROM meta_account WHERE admin_user=$1"
        row = await cls.db.fetchrow(q, admin_user)

        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def get_all_account_ids(cls) -> List[str]:
        q = f"SELECT {cls._columns} FROM meta_account WHERE account_id IS NOT NULL"
        rows = await cls.db.fetch(q)

        if not rows:
            return []
        return [cls._from_row(account).account_id for account in rows]

    @classmethod
    async def get_all_wb_apps(cls) -> List[WsBusinessID]:
        """Compatibility alias for older WhatsApp provisioning code."""
        return await cls.get_all_account_ids()
