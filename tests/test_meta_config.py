from meta_cloud_bridge.meta.config import load_meta_config
from meta_cloud_bridge.meta.types import MetaChannel


def test_load_meta_accounts_from_plain_mapping():
    config = {
        "meta": {
            "graph_base_url": "https://graph.facebook.com",
            "instagram_base_url": "https://graph.instagram.com",
            "version": "v25.0",
            "app_secret": "secret",
            "verify_token": "verify",
            "accounts": [
                {
                    "id": "wa-main",
                    "channel": "whatsapp",
                    "waba_id": "waba-1",
                    "phone_number_id": "phone-1",
                    "access_token": "token-wa",
                    "owner_mxid": "@admin:example.com",
                },
                {
                    "id": "ig-login",
                    "channel": "instagram_login",
                    "instagram_user_id": "ig-1",
                    "access_token": "token-ig",
                },
            ],
        }
    }

    meta_config = load_meta_config(config)

    assert meta_config.app_secret == "secret"
    assert meta_config.verify_token == "verify"
    assert len(meta_config.accounts) == 2
    whatsapp = meta_config.account_for_key("waba-1")
    assert whatsapp.channel is MetaChannel.WHATSAPP
    assert whatsapp.legacy_business_id == "waba-1"
    assert whatsapp.send_asset_id == "phone-1"

    instagram_login = meta_config.account_for_key("ig-login")
    assert instagram_login.channel is MetaChannel.INSTAGRAM_LOGIN
    assert instagram_login.graph_base_url == "https://graph.instagram.com"
