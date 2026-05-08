from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

import asyncpg
from attr import dataclass
from mautrix.types import SyncToken, UserID
from mautrix.util.async_db import Database
from yarl import URL

fake_db = Database.create("") if TYPE_CHECKING else None


@dataclass
class Puppet:
    db: ClassVar[Database] = fake_db

    phone_id: str
    app_business_id: str
    display_name: str | None
    is_registered: bool
    custom_mxid: UserID | None
    access_token: str | None
    next_batch: SyncToken | None
    base_url: URL | None

    @property
    def remote_user_id(self) -> str:
        return self.phone_id

    @property
    def account_id(self) -> str:
        return self.app_business_id

    @property
    def _values(self):
        return (
            self.phone_id,
            self.app_business_id,
            self.display_name,
            self.is_registered,
            self.custom_mxid,
            self.access_token,
            self.next_batch,
            str(self.base_url) if self.base_url else None,
        )

    _columns = (
        "remote_user_id AS phone_id, account_id AS app_business_id, display_name, "
        "is_registered, custom_mxid, access_token, next_batch, base_url"
    )
    _insert_columns = (
        "remote_user_id, account_id, display_name, is_registered, custom_mxid, access_token, "
        "next_batch, base_url"
    )

    @classmethod
    def _from_row(cls, row: asyncpg.Record) -> Puppet:
        return cls(**row)

    async def insert(self) -> None:
        q = f"""
            INSERT INTO puppet ({self._insert_columns})
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
        """
        await self.db.execute(q, *self._values)

    async def update(self) -> None:
        q = """
            UPDATE puppet SET display_name=$3, is_registered=$4,
            custom_mxid=$5, access_token=$6, next_batch=$7, base_url=$8
            WHERE remote_user_id=$1 AND account_id=$2
        """
        await self.db.execute(q, *self._values)

    @classmethod
    async def get_by_phone_id(
        cls, phone_id: str, app_business_id: str | None = None
    ) -> Puppet | None:
        q = f"""
            SELECT {cls._columns}
            FROM puppet WHERE remote_user_id=$1 AND ($2::text IS NULL OR account_id=$2)
            ORDER BY account_id LIMIT 1
        """
        row = await cls.db.fetchrow(q, phone_id, app_business_id)
        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def get_by_remote_user_id(
        cls, remote_user_id: str, account_id: str | None = None
    ) -> Puppet | None:
        return await cls.get_by_phone_id(remote_user_id, account_id)

    @classmethod
    async def get_by_custom_mxid(cls, mxid: UserID) -> Puppet | None:
        q = f"""
            SELECT {cls._columns}
            FROM puppet WHERE custom_mxid=$1
        """
        row = await cls.db.fetchrow(q, mxid)
        if not row:
            return None
        return cls._from_row(row)

    @classmethod
    async def all_with_custom_mxid(cls) -> list[Puppet]:
        q = f"""
            SELECT {cls._columns}
            FROM puppet WHERE custom_mxid IS NOT NULL
        """
        rows = await cls.db.fetch(q)
        return [cls._from_row(row) for row in rows]
