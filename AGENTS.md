# AGENTS.md

## Project: meta-cloud-bridge

A Matrix bridge for Meta's official messaging APIs (WhatsApp, Instagram, Facebook Messenger) via `graph.facebook.com`.

## Origin

Forked from [iKonoTelecomunicaciones/whatsapp-cloud](https://github.com/iKonoTelecomunicaciones/whatsapp-cloud) (MIT License).
All credit for the original WhatsApp Cloud API bridge goes to the iKono team.

## Intent

Extend the existing WhatsApp Cloud API bridge into a **unified multichannel bridge** that supports all three Meta messaging platforms through their official APIs:

- **WhatsApp** — `POST graph.facebook.com/{phone_id}/messages` (already working)
- **Instagram DM** — `POST graph.facebook.com/{ig_user_id}/messages` (to be added)
- **Facebook Messenger** — `POST graph.facebook.com/me/messages` (to be added)

## Architecture Goals

1. Abstract the shared Graph API layer (auth, webhooks, media upload/download)
2. Keep channel-specific logic in separate modules (templates, flows, ice breakers, etc.)
3. Single webhook endpoint that routes by channel based on payload
4. One Meta App → multiple channels under the same Matrix bridge

## Key Decisions

- Use only **official Meta APIs** — no puppeting, no reverse-engineering, no ban risk
- Stay on **mautrix-python** as the Matrix bridge framework (same as upstream)
- Maintain compatibility with upstream iKono changes where possible
- If iKono wants this upstream, the project can move to their org

## Development

```bash
# Python (use uv)
uv venv && source .venv/bin/activate
uv pip install -e .
```

## Commands

```bash
# Run the bridge
python -m whatsapp_matrix

# Docker
docker build -t meta-cloud-bridge .
```
