from __future__ import annotations

from asyncio import AbstractEventLoop

from meta_cloud_bridge.config import Config
from meta_cloud_bridge.meta.config import load_meta_config
from meta_cloud_bridge.meta.webhook import MetaHandler


class WhatsappHandler(MetaHandler):
    """Compatibility wrapper for the old WhatsApp-only webhook handler name.

    The bridge now uses :class:`meta_cloud_bridge.meta.webhook.MetaHandler`, which
    handles WhatsApp, Messenger, Instagram Page-linked messaging, and Instagram
    Login messaging through one signed `/receive` webhook endpoint.
    """

    def __init__(
        self, loop: AbstractEventLoop | None = None, config: Config | None = None
    ) -> None:
        if config is None:
            raise ValueError("config is required")
        super().__init__(loop=loop, config=load_meta_config(config))
