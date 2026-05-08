from aiohttp import ClientSession
from mautrix.bridge import Bridge
from mautrix.types import RoomID, UserID

from meta_cloud_bridge.meta.config import load_meta_config
from meta_cloud_bridge.meta.webhook import MetaHandler

from . import commands
from .config import Config
from .db import MetaAccountRecord
from .db import init as init_db
from .db import upgrade_table
from .matrix import MatrixHandler
from .portal import Portal
from .puppet import Puppet
from .user import User
from .version import linkified_version, version
from .web import ProvisioningAPI


class MetaCloudBridge(Bridge):
    name = "meta-cloud-bridge"
    module = "meta_cloud_bridge"
    command = "meta-cloud-bridge"
    description = "A Matrix bridge for Meta's official messaging APIs."
    repo_url = "https://github.com/EmiliaVision/meta-cloud-bridge"
    version = version
    markdown_version = linkified_version
    config_class = Config
    matrix_class = MatrixHandler
    upgrade_table = upgrade_table

    config: Config
    meta: MetaHandler
    session: ClientSession

    provisioning_api: ProvisioningAPI

    def preinit(self) -> None:
        super().preinit()

    def prepare_db(self) -> None:
        super().prepare_db()
        init_db(self.db)

    def prepare_bridge(self) -> None:
        self.meta_config = load_meta_config(self.config)
        self.meta = MetaHandler(loop=self.loop, config=self.meta_config)
        self.session = ClientSession(loop=self.loop)
        super().prepare_bridge()
        self.az.app.add_subapp(self.meta_config.webhook_path, self.meta.app)
        cfg = self.config["bridge.provisioning"]
        self.provisioning_api = ProvisioningAPI(
            config=self.config,
            shared_secret=cfg["shared_secret"],
        )
        self.az.app.add_subapp(cfg["prefix"], self.provisioning_api.app)

    async def start(self) -> None:
        User.init_cls(self)
        self.add_startup_actions(Puppet.init_cls(self))
        Portal.init_cls(self)
        await self._sync_configured_meta_accounts()
        await super().start()

    async def _sync_configured_meta_accounts(self) -> None:
        for account in self.meta_config.accounts:
            existing = await MetaAccountRecord.get_by_account_id(account.account_key)
            if existing:
                continue
            await MetaAccountRecord.insert(
                name=account.label or account.id,
                admin_user=str(account.owner_mxid or "@meta-cloud-bridge:localhost"),
                account_id=account.account_key,
                channel=account.channel.value,
                asset_id=account.asset_id,
                send_asset_id=account.send_asset_id,
                access_token=account.access_token,
            )

    def prepare_stop(self) -> None:
        self.log.debug("Stopping puppet syncers")
        for puppet in Puppet.by_custom_mxid.values():
            puppet.stop()

    async def get_user(self, user_id: UserID, create: bool = True) -> User:
        return await User.get_by_mxid(user_id, create=create)

    async def get_portal(self, room_id: RoomID) -> Portal:
        return await Portal.get_by_mxid(room_id)

    async def get_puppet(self, user_id: UserID, create: bool = False) -> Puppet:
        return await Puppet.get_by_mxid(user_id, create=create)

    async def get_double_puppet(self, user_id: UserID) -> Puppet:
        return await Puppet.get_by_custom_mxid(user_id)

    def is_bridge_ghost(self, user_id: UserID) -> bool:
        return bool(Puppet.get_id_from_mxid(user_id))

    async def count_logged_in_users(self) -> int:
        return len([user for user in User.by_business_id.values() if user.app_business_id])


WhatsappBridge = MetaCloudBridge


def main() -> None:
    MetaCloudBridge().run()


if __name__ == "__main__":
    main()
