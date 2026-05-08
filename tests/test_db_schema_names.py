from pathlib import Path

from meta_cloud_bridge.db.message import Message
from meta_cloud_bridge.db.meta_account import MetaAccountRecord
from meta_cloud_bridge.db.portal import Portal
from meta_cloud_bridge.db.puppet import Puppet
from meta_cloud_bridge.db.reaction import Reaction
from meta_cloud_bridge.db.user import User


def test_runtime_db_models_write_generic_physical_columns() -> None:
    assert MetaAccountRecord._columns == (
        "account_id, channel, asset_id, send_asset_id, name, admin_user, access_token"
    )
    assert Portal._insert_columns == "remote_user_id, account_id, mxid, relay_user_id"
    assert Puppet._insert_columns.startswith("remote_user_id, account_id")
    assert User._insert_columns == "mxid, account_id, notice_room"
    assert "remote_message_id" in Message._insert_columns
    assert "remote_message_id" in Reaction._insert_columns

    physical_writes = "\n".join(
        [
            MetaAccountRecord._columns,
            Portal._insert_columns,
            Puppet._insert_columns,
            User._insert_columns,
            Message._insert_columns,
            Reaction._insert_columns,
        ]
    )
    assert "wb_application" not in physical_writes
    assert "whatsapp_message_id" not in physical_writes
    assert "app_business_id" not in physical_writes
    assert "wb_phone_id" not in physical_writes


def test_initial_upgrade_schema_uses_generic_meta_names() -> None:
    upgrade_source = Path("meta_cloud_bridge/db/upgrade.py").read_text()
    initial_schema = upgrade_source.split("Reserved migration slot", maxsplit=1)[0]

    assert "CREATE TABLE meta_account" in initial_schema
    assert "remote_user_id" in initial_schema
    assert "remote_message_id" in initial_schema
    assert "account_id" in initial_schema

    assert "wb_application" not in initial_schema
    assert "whatsapp_message_id" not in initial_schema
    assert "app_business_id" not in initial_schema
    assert "wb_phone_id" not in initial_schema
