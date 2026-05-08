from asyncpg import Connection
from mautrix.util.async_db import UpgradeTable

upgrade_table = UpgradeTable()


async def _table_exists(conn: Connection, table_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.tables
                WHERE table_schema = current_schema() AND table_name = $1
            )
            """,
            table_name,
        )
    )


async def _column_exists(conn: Connection, table_name: str, column_name: str) -> bool:
    return bool(
        await conn.fetchval(
            """
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_schema = current_schema()
                  AND table_name = $1
                  AND column_name = $2
            )
            """,
            table_name,
            column_name,
        )
    )


async def _rename_column_if_exists(
    conn: Connection, table_name: str, old_name: str, new_name: str
) -> None:
    if await _column_exists(conn, table_name, old_name) and not await _column_exists(
        conn, table_name, new_name
    ):
        await conn.execute(
            f'ALTER TABLE "{table_name}" RENAME COLUMN "{old_name}" TO "{new_name}"'
        )


async def _add_column_if_missing(conn: Connection, table_name: str, column_sql: str) -> None:
    column_name = column_sql.split()[0].strip('"')
    if not await _column_exists(conn, table_name, column_name):
        await conn.execute(f'ALTER TABLE "{table_name}" ADD COLUMN {column_sql}')


@upgrade_table.register(description="Initial Meta Cloud Bridge schema")
async def upgrade_v1(conn: Connection) -> None:
    await conn.execute("""CREATE TABLE meta_account (
            account_id      TEXT PRIMARY KEY,
            channel         TEXT NOT NULL DEFAULT 'whatsapp',
            asset_id        TEXT,
            send_asset_id   TEXT,
            name            VARCHAR(255),
            admin_user      VARCHAR(255),
            access_token    TEXT
        )""")
    await conn.execute("""CREATE TABLE portal (
            remote_user_id  TEXT NOT NULL,
            account_id      TEXT NOT NULL,
            mxid            VARCHAR(255),
            relay_user_id   VARCHAR(255),
            encrypted       BOOLEAN DEFAULT false,
            PRIMARY KEY (remote_user_id, account_id)
        )""")
    await conn.execute("""CREATE TABLE puppet (
            remote_user_id  TEXT NOT NULL,
            account_id      TEXT NOT NULL,
            display_name    TEXT,
            is_registered   BOOLEAN NOT NULL DEFAULT false,
            custom_mxid     VARCHAR(255),
            access_token    TEXT,
            next_batch      TEXT,
            base_url        TEXT,
            PRIMARY KEY (remote_user_id, account_id)
        )""")
    await conn.execute("""CREATE TABLE matrix_user (
            mxid            VARCHAR(255) PRIMARY KEY,
            account_id      TEXT,
            notice_room     TEXT
        )""")
    await conn.execute("""CREATE TABLE message (
            event_mxid        VARCHAR(255) PRIMARY KEY,
            room_id           VARCHAR(255) NOT NULL,
            remote_user_id    TEXT NOT NULL,
            sender            VARCHAR(255) NOT NULL,
            remote_message_id TEXT NOT NULL,
            account_id        TEXT NOT NULL,
            created_at        TIMESTAMP WITH TIME ZONE NOT NULL,
            UNIQUE (event_mxid, room_id),
            UNIQUE (remote_message_id)
        )""")
    await conn.execute("""CREATE TABLE reaction (
            event_mxid        VARCHAR(255) PRIMARY KEY,
            room_id           VARCHAR(255) NOT NULL,
            sender            VARCHAR(255) NOT NULL,
            remote_message_id TEXT NOT NULL,
            reaction          VARCHAR(255),
            created_at        TIMESTAMP WITH TIME ZONE NOT NULL,
            UNIQUE (event_mxid, room_id)
        )""")

    await conn.execute("""ALTER TABLE message ADD CONSTRAINT fk_message_meta_account
        FOREIGN KEY (account_id) REFERENCES meta_account (account_id)""")
    await conn.execute("""ALTER TABLE portal ADD CONSTRAINT fk_portal_meta_account
        FOREIGN KEY (account_id) REFERENCES meta_account (account_id)""")
    await conn.execute("""ALTER TABLE matrix_user ADD CONSTRAINT fk_matrix_user_meta_account
        FOREIGN KEY (account_id) REFERENCES meta_account (account_id)""")
    await conn.execute("""ALTER TABLE puppet ADD CONSTRAINT fk_puppet_meta_account
        FOREIGN KEY (account_id) REFERENCES meta_account (account_id)""")
    await conn.execute("""ALTER TABLE message ADD CONSTRAINT fk_message_portal
        FOREIGN KEY (remote_user_id, account_id) REFERENCES portal (remote_user_id, account_id)""")
    await conn.execute("""ALTER TABLE reaction ADD CONSTRAINT fk_reaction_message
        FOREIGN KEY (remote_message_id) REFERENCES message (remote_message_id)
        ON DELETE CASCADE""")


@upgrade_table.register(description="Reserved migration slot from the WhatsApp schema")
async def upgrade_v2(conn: Connection) -> None:
    # The Meta schema in v1 already uses a composite portal key.
    pass


@upgrade_table.register(description="Reserved migration slot from the WhatsApp puppet schema")
async def upgrade_v3(conn: Connection) -> None:
    # The Meta schema in v1 already scopes puppets by account.
    pass


@upgrade_table.register(
    description="Rename legacy WhatsApp tables and columns to generic Meta names"
)
async def upgrade_v4(conn: Connection) -> None:
    """Migrate databases created by pre-Meta Cloud Bridge revisions.

    Fresh installs already use the generic schema from v1. This migration is kept
    for anyone who ran an intermediate build that still created WhatsApp-named
    physical tables/columns.
    """

    # Drop old foreign keys before renaming table/column identifiers. All drops are
    # idempotent so the migration is a no-op on fresh Meta schemas.
    for table_name, constraint_name in (
        ("message", "fk_message_wb_application_app_business_id"),
        ("message", "fk_message_portal_phone_id"),
        ("message", "fk_message_portal_phone_id_business_id"),
        ("portal", "fk_portal_wb_application_app_business_id"),
        ("matrix_user", "fk_matrix_user_wb_application_app_business_id"),
        ("puppet", "fk_puppet_wb_application_app_business_id"),
        ("reaction", "fk_message_whatsapp_message_id"),
    ):
        if await _table_exists(conn, table_name):
            await conn.execute(
                f'ALTER TABLE "{table_name}" DROP CONSTRAINT IF EXISTS "{constraint_name}"'
            )

    if await _table_exists(conn, "wb_application") and not await _table_exists(
        conn, "meta_account"
    ):
        await conn.execute('ALTER TABLE "wb_application" RENAME TO "meta_account"')

    if await _table_exists(conn, "meta_account"):
        await _rename_column_if_exists(conn, "meta_account", "business_id", "account_id")
        await _rename_column_if_exists(conn, "meta_account", "wb_phone_id", "asset_id")
        await _rename_column_if_exists(conn, "meta_account", "page_access_token", "access_token")
        await _add_column_if_missing(
            conn, "meta_account", "channel TEXT NOT NULL DEFAULT 'whatsapp'"
        )
        await _add_column_if_missing(conn, "meta_account", "send_asset_id TEXT")
        await conn.execute("""
            UPDATE meta_account
            SET send_asset_id = asset_id
            WHERE send_asset_id IS NULL
              AND channel = 'whatsapp'
              AND asset_id IS NOT NULL
            """)
        await conn.execute("""
            UPDATE meta_account
            SET asset_id = account_id
            WHERE channel = 'whatsapp'
              AND account_id IS NOT NULL
              AND send_asset_id IS NOT NULL
            """)

    for table_name in ("portal", "puppet", "message"):
        if await _table_exists(conn, table_name):
            await _rename_column_if_exists(conn, table_name, "phone_id", "remote_user_id")
            await _rename_column_if_exists(conn, table_name, "app_business_id", "account_id")

    if await _table_exists(conn, "matrix_user"):
        await _rename_column_if_exists(conn, "matrix_user", "app_business_id", "account_id")

    if await _table_exists(conn, "message"):
        await _rename_column_if_exists(conn, "message", "whatsapp_message_id", "remote_message_id")

    if await _table_exists(conn, "reaction"):
        await _rename_column_if_exists(
            conn, "reaction", "whatsapp_message_id", "remote_message_id"
        )

    # Normalize primary keys that may have been created by older revisions.
    # Drop the generic portal FK first too, otherwise PostgreSQL will not allow
    # replacing the referenced primary key on fresh generic schemas.
    if await _table_exists(conn, "message"):
        await conn.execute("""ALTER TABLE message DROP CONSTRAINT IF EXISTS fk_message_portal""")

    if await _table_exists(conn, "portal"):
        await conn.execute('ALTER TABLE "portal" DROP CONSTRAINT IF EXISTS "portal_pkey"')
        await conn.execute("""ALTER TABLE portal
            ADD PRIMARY KEY (remote_user_id, account_id)""")

    if await _table_exists(conn, "puppet"):
        await conn.execute('ALTER TABLE "puppet" DROP CONSTRAINT IF EXISTS "puppet_pkey"')
        await conn.execute("""ALTER TABLE puppet
            ADD PRIMARY KEY (remote_user_id, account_id)""")

    # Recreate foreign keys with generic names. If duplicate data prevents a
    # constraint from being created, asyncpg will surface the issue during startup.
    if await _table_exists(conn, "message") and await _table_exists(conn, "meta_account"):
        await conn.execute(
            """ALTER TABLE message DROP CONSTRAINT IF EXISTS fk_message_meta_account"""
        )
        await conn.execute("""ALTER TABLE message ADD CONSTRAINT fk_message_meta_account
            FOREIGN KEY (account_id) REFERENCES meta_account (account_id)""")

    if await _table_exists(conn, "portal") and await _table_exists(conn, "meta_account"):
        await conn.execute(
            """ALTER TABLE portal DROP CONSTRAINT IF EXISTS fk_portal_meta_account"""
        )
        await conn.execute("""ALTER TABLE portal ADD CONSTRAINT fk_portal_meta_account
            FOREIGN KEY (account_id) REFERENCES meta_account (account_id)""")

    if await _table_exists(conn, "matrix_user") and await _table_exists(conn, "meta_account"):
        await conn.execute(
            """ALTER TABLE matrix_user DROP CONSTRAINT IF EXISTS fk_matrix_user_meta_account"""
        )
        await conn.execute("""ALTER TABLE matrix_user ADD CONSTRAINT fk_matrix_user_meta_account
            FOREIGN KEY (account_id) REFERENCES meta_account (account_id)""")

    if await _table_exists(conn, "puppet") and await _table_exists(conn, "meta_account"):
        await conn.execute(
            """ALTER TABLE puppet DROP CONSTRAINT IF EXISTS fk_puppet_meta_account"""
        )
        await conn.execute("""ALTER TABLE puppet ADD CONSTRAINT fk_puppet_meta_account
            FOREIGN KEY (account_id) REFERENCES meta_account (account_id)""")

    if await _table_exists(conn, "message") and await _table_exists(conn, "portal"):
        await conn.execute("""ALTER TABLE message DROP CONSTRAINT IF EXISTS fk_message_portal""")
        await conn.execute(
            """ALTER TABLE message ADD CONSTRAINT fk_message_portal
            FOREIGN KEY (remote_user_id, account_id) REFERENCES portal (remote_user_id, account_id)"""
        )

    if await _table_exists(conn, "reaction") and await _table_exists(conn, "message"):
        await conn.execute(
            """ALTER TABLE reaction DROP CONSTRAINT IF EXISTS fk_reaction_message"""
        )
        await conn.execute("""ALTER TABLE reaction ADD CONSTRAINT fk_reaction_message
            FOREIGN KEY (remote_message_id) REFERENCES message (remote_message_id)
            ON DELETE CASCADE""")
