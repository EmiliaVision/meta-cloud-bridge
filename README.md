# meta-cloud-bridge

A Matrix bridge for **Meta's official messaging APIs** — WhatsApp, Instagram DM, and Facebook Messenger — via `graph.facebook.com`.

> **Built on top of [iKonoTelecomunicaciones/whatsapp-cloud](https://github.com/iKonoTelecomunicaciones/whatsapp-cloud)**
> All credit for the original WhatsApp Cloud API ↔ Matrix bridge goes to the [iKono Telecomunicaciones](https://github.com/iKonoTelecomunicaciones) team.
> This project extends their work to support all three Meta messaging channels.

## Why

Meta offers three messaging APIs that share the same infrastructure (`graph.facebook.com`), the same webhook model, and the same authentication pattern. Yet no single bridge exists that connects all three to Matrix using the official APIs.

This project aims to be that bridge.

## Supported Channels

| Channel | API | Endpoint | Status |
|---------|-----|----------|--------|
| WhatsApp | WhatsApp Cloud API | `/<PHONE_NUMBER_ID>/messages` | ✅ Implemented; E2E pending |
| Instagram DM, Page-linked | Instagram Messaging API via Messenger Platform | `/<PAGE_ID>/messages` | ✅ Implemented; E2E pending |
| Instagram DM, Instagram Login | Instagram API with Instagram Login | `graph.instagram.com/<IG_ID>/messages` | ✅ Implemented; E2E pending |
| Facebook Messenger | Messenger Platform | `/<PAGE_ID>/messages` or `/me/messages` | ✅ Implemented; E2E pending |

## Key Features (inherited from iKono)

- Official Meta Cloud API — no ban risk, no puppeting
- Webhook with HMAC signature verification
- Media upload/download via Graph API
- WhatsApp message templates
- Interactive messages (buttons, lists, flows)
- Message editing (WhatsApp → Matrix)
- Read receipts

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_ORG/meta-cloud-bridge.git
cd meta-cloud-bridge

# Install dependencies and create .venv
uv sync

# Optional: install developer tools too
uv sync --dev

# Configure
cp meta_cloud_bridge/example-config.yaml config.yaml
# Edit config.yaml with your Meta App credentials

# Run
uv run meta-cloud-bridge
```

Docker image: `docker build -t meta-cloud-bridge .`

This repository targets **Python 3.14** and uses **uv** as the only dependency and lockfile manager.

## Configuration

Register a Meta App with WhatsApp (and optionally Instagram/Messenger) products enabled:

1. Go to [developers.facebook.com](https://developers.facebook.com/)
2. Create a Business app
3. Add WhatsApp / Instagram / Messenger products
4. Get your Phone Number ID, Access Token, and App Secret
5. Configure the webhook pointing to your bridge

## Architecture

```
graph.facebook.com
    ├── /{phone_number_id}/messages → WhatsApp
    ├── /{page_id}/messages         → Messenger / page-linked Instagram DM
    └── graph.instagram.com/{ig_id}/messages → Instagram Login DM
         │
         ▼
   meta-cloud-bridge (single webhook, single process)
         │
         ▼
   Matrix Homeserver (Synapse, Dendrite, Conduit)
```

## Acknowledgments

- **[iKono Telecomunicaciones SAS](https://github.com/iKonoTelecomunicaciones)** — Original `whatsapp-cloud` bridge (MIT License)
- **[mautrix-python](https://github.com/mautrix/python)** — Matrix bridge framework
- **[Meta Business Messaging](https://developers.facebook.com/docs/business-messaging/)** — Official APIs

## License

MIT — see [LICENSE.md](LICENSE.md)
