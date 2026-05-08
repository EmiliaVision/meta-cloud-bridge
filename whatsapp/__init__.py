"""WhatsApp Cloud API compatibility package.

The multichannel bridge uses :mod:`meta_cloud_bridge.meta` for shared Graph API
logic. This package keeps the original WhatsApp-specific data models and helper
client available without importing webhook modules at package import time.
"""

from .types import WhatsappPhone, WsBusinessID

__all__ = ["WhatsappPhone", "WsBusinessID"]
