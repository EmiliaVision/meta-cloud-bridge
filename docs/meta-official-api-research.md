# Research: Official Meta APIs for meta-cloud-bridge

Date: 2026-05-07

Goal of the fork: extend the current WhatsApp Cloud API bridge into a multichannel Matrix bridge for WhatsApp, Instagram DM, and Facebook Messenger using only official Meta APIs (`graph.facebook.com` / `graph.instagram.com`) while staying on `mautrix-python`.

## Official sources reviewed

### WhatsApp Business Platform / Cloud API

- Send Messages / Messages reference: <https://developers.facebook.com/docs/whatsapp/cloud-api/reference/messages>
- Webhooks overview: <https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks>
- Webhook payload examples: <https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/payload-examples>
- Media reference: <https://developers.facebook.com/docs/whatsapp/cloud-api/reference/media>
- Set up Webhooks: <https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-webhooks>
- Permission `whatsapp_business_messaging`: <https://developers.facebook.com/docs/permissions/reference/whatsapp_business_messaging/>

### Messenger Platform

- Messenger Platform overview: <https://developers.facebook.com/docs/messenger-platform/>
- Send a Message: <https://developers.facebook.com/docs/messenger-platform/send-messages/>
- Webhooks for Messenger Platform: <https://developers.facebook.com/docs/messenger-platform/webhooks/>
- Page `subscribed_apps`: <https://developers.facebook.com/docs/graph-api/reference/page/subscribed_apps/>
- Page `message_attachments`: <https://developers.facebook.com/docs/graph-api/reference/page/message_attachments/>
- Permission `pages_messaging`: <https://developers.facebook.com/docs/permissions/reference/pages_messaging/>
- Permission `pages_manage_metadata`: <https://developers.facebook.com/docs/permissions/reference/pages_manage_metadata/>

### Instagram Messaging

There are two official modes that matter:

1. **Instagram Messaging API via Messenger Platform** for Instagram professional accounts linked to a Facebook Page:
   - Overview: <https://developers.facebook.com/docs/messenger-platform/instagram>
   - Send a Message: <https://developers.facebook.com/docs/messenger-platform/instagram/features/send-message>
   - Webhooks are handled as Messenger/Page webhooks: <https://developers.facebook.com/docs/messenger-platform/webhooks/>
   - Permission `instagram_manage_messages`: <https://developers.facebook.com/docs/permissions/reference/instagram_manage_messages/>

2. **Instagram API with Instagram Login** for Instagram professional accounts not linked to a Facebook Page:
   - Messaging API: <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/>
   - Webhooks: <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/messaging-api/webhooks/>
   - Permission `instagram_business_manage_messages`: <https://developers.facebook.com/docs/permissions/reference/instagram_business_manage_messages/>

### Graph API webhooks / security

- Webhooks from Meta: <https://developers.facebook.com/docs/graph-api/webhooks/>
- Secure requests / signature verification: <https://developers.facebook.com/docs/graph-api/guides/secure-requests/>

## Key findings by channel

### 1. WhatsApp Cloud API

**Sending messages**

Current official endpoint:

```http
POST https://graph.facebook.com/<API_VERSION>/<WHATSAPP_BUSINESS_PHONE_NUMBER_ID>/messages
Authorization: Bearer <ACCESS_TOKEN>
Content-Type: application/json
```

Common payload:

```json
{
  "messaging_product": "whatsapp",
  "recipient_type": "individual",
  "to": "<WHATSAPP_USER_PHONE_NUMBER>",
  "type": "text",
  "text": {
    "preview_url": true,
    "body": "Hello"
  }
}
```

The response only confirms that Meta accepted the request. Real delivery status arrives later through `messages`/`statuses` webhooks.

**Webhooks**

Top-level `object`:

```json
"whatsapp_business_account"
```

Main structure:

```json
{
  "object": "whatsapp_business_account",
  "entry": [
    {
      "id": "<WABA_ID>",
      "changes": [
        {
          "field": "messages",
          "value": {
            "messaging_product": "whatsapp",
            "metadata": {
              "display_phone_number": "...",
              "phone_number_id": "..."
            },
            "contacts": [{ "wa_id": "...", "profile": { "name": "..." } }],
            "messages": [{ "from": "...", "id": "wamid...", "type": "text", "text": { "body": "..." } }]
          }
        }
      ]
    }
  ]
}
```

Relevant events:

- Incoming messages: `value.messages`
- Status/read/delivery/failure: `value.statuses`
- Echoes and SMB echoes exist in the docs; the current code already handles `message_echoes`.
- Required permission for message webhooks: `whatsapp_business_messaging`. Other account-management webhooks usually require `whatsapp_business_management`.

**Media**

- Upload: `POST /<PHONE_NUMBER_ID>/media` with multipart `messaging_product=whatsapp` and `file=@...;type=<MIME_TYPE>`; returns `{ "id": "<MEDIA_ID>" }`.
- Send media: reference the `MEDIA_ID` in `image.id`, `video.id`, `audio.id`, `document.id`, etc.
- Get media URL: `GET /<MEDIA_ID>?phone_number_id=<PHONE_NUMBER_ID>` with bearer token. URLs expire after 5 minutes.
- Download: `GET <MEDIA_URL>` with bearer token.

### 2. Facebook Messenger Platform

**Sending messages**

Official endpoint:

```http
POST https://graph.facebook.com/<API_VERSION>/<PAGE_ID>/messages
# or https://graph.facebook.com/<API_VERSION>/me/messages with a Page access token
```

Requirements:

- Page ID of the sending Page.
- Page access token.
- Recipient PSID (`recipient.id`).
- `pages_messaging` and the required Page tasks/permissions.
- Messenger uses `messaging_type`, usually `RESPONSE` within the standard 24-hour messaging window.

Text payload:

```json
{
  "recipient": { "id": "<PSID>" },
  "messaging_type": "RESPONSE",
  "message": { "text": "Hello, world!" }
}
```

Media payload by URL:

```json
{
  "recipient": { "id": "<PSID>" },
  "messaging_type": "RESPONSE",
  "message": {
    "attachment": {
      "type": "image",
      "payload": {
        "url": "https://example.com/image.jpg",
        "is_reusable": true
      }
    }
  }
}
```

**Media / attachment upload**

Graph Page edge:

```http
POST /<PAGE_ID>/message_attachments
```

Uses:

- Upload an asset from a URL or from a file.
- Returns `{ "attachment_id": "..." }` for reuse.
- The `platform` parameter supports `INSTAGRAM` or `MESSENGER` according to the edge docs.

**Webhooks**

Top-level `object`:

```json
"page"
```

Main structure:

```json
{
  "object": "page",
  "entry": [
    {
      "id": "<PAGE_ID>",
      "time": 1458692752478,
      "messaging": [
        {
          "sender": { "id": "<PSID>" },
          "recipient": { "id": "<PAGE_ID>" },
          "timestamp": 1458692752478,
          "message": { "mid": "...", "text": "hello" }
        }
      ]
    }
  ]
}
```

Important events/subscriptions:

- `messages`: inbound customer messages.
- `message_echoes`: business sent a message. Messenger only; Instagram echoes arrive through `messages`.
- `message_deliveries`: Messenger deliveries.
- `message_reads`: Messenger reads.
- `message_reactions`, `messaging_postbacks`, `messaging_referrals`, `standby`, etc.

Meta requires a `200 OK` response in 5 seconds or less. If delivery fails, Meta retries. After 15 minutes it alerts the developer account, and after 1 hour it may unsubscribe the app/Page. Deduplication by message ID / event ID is required.

### 3. Instagram Messaging API via Messenger Platform (IG account linked to Page)

This is likely the best fit for a “one Meta App + Messenger + Instagram” bridge because it shares Page access tokens, Send API semantics, and `object=page` webhooks.

**Sending messages**

Current official endpoint in Instagram Messaging docs:

```http
POST https://graph.facebook.com/<API_VERSION>/<PAGE_ID>/messages
# or /me/messages with a Page access token
```

Requirements:

- Facebook Page linked to the Instagram professional account.
- Page access token requested by a user who has the `MESSAGE` task on that Page.
- Recipient: IGSID (Instagram-scoped ID) received from a webhook.
- Permission: `instagram_manage_messages`.

Text payload:

```json
{
  "recipient": { "id": "<IGSID>" },
  "message": { "text": "TEXT-OR-LINK" }
}
```

Media:

- Image/audio/video/file by URL or by `attachment_id`.
- Text limit: 1000 bytes/characters depending on the current docs wording.
- Media limits: image png/jpeg 8MB; audio 25MB; video 25MB; PDF file 25MB.

Reactions/replies:

- React: `sender_action=react` + `payload.message_id` + `payload.reaction`.
- Unreact: `sender_action=unreact`.
- Reply: include `reply_to: { "mid": "<MESSAGE_ID>" }`.

**Webhooks**

Payloads use the Messenger/Page webhook shape:

```json
{
  "object": "page",
  "entry": [
    {
      "id": "<PAGE_ID>",
      "messaging": [
        {
          "sender": { "id": "<IGSID>" },
          "recipient": { "id": "<PAGE_ID_OR_IG_ID?>" },
          "timestamp": 123,
          "message": { "mid": "...", "text": "..." }
        }
      ]
    }
  ]
}
```

Relevant fields:

- `messages`
- `messaging_postbacks`
- `message_reactions`
- `messaging_seen` for Instagram read receipts
- `messaging_referrals`, `messaging_optins`, `standby`

Official note: for Instagram Messaging, `messages` also includes echoes for messages sent by the Instagram professional account. There is no separate `message_echoes` field like Messenger has.

### 4. Instagram API with Instagram Login (IG account not linked to Page)

Important: current docs separate this mode from Messenger Platform. In this mode the base URL is not `graph.facebook.com`, but:

```http
https://graph.instagram.com/<API_VERSION>/<IG_ID>/messages
# or /me/messages
```

Requirements:

- Instagram User access token.
- `instagram_business_basic`.
- `instagram_business_manage_messages`.
- Instagram Messaging webhook subscriptions: `messages`, `messaging_optins`, `messaging_postbacks`, `messaging_reactions`, `messaging_referrals`, `messaging_seen`.

This mode should be supported as a separate configuration path. It should not be conflated with Page-linked Instagram Messaging.

## Shared webhook security

Meta uses two distinct mechanisms:

1. **Initial GET verification**
   - Query params: `hub.mode=subscribe`, `hub.verify_token`, `hub.challenge`.
   - If the token matches, respond with the challenge and status 200.

2. **POST payload validation**
   - Header: `X-Hub-Signature-256: sha256=<hex>`.
   - HMAC-SHA256 using the App Secret and the raw request body.
   - Comparison must be constant-time.
   - In `aiohttp`, read `await request.read()` before JSON parsing so the signature is computed over the exact raw bytes.

All handlers should return 200 quickly. Heavy processing should be moved to background tasks if needed. Deduplicate by `wamid`, `mid`, status ID, etc.

## Current code observations

Key files:

- `whatsapp/api.py`: `WhatsappClient` wraps WhatsApp send/media/template calls.
- `meta_cloud_bridge/meta/webhook.py`: `MetaHandler` mounts `/receive`, verifies the token, validates `X-Hub-Signature-256`, deduplicates, and routes Meta webhooks.
- `whatsapp/webhook.py`: compatibility wrapper that delegates to `MetaHandler`.
- `whatsapp/data.py`: dataclasses/serialization for WhatsApp-specific payloads.
- `meta_cloud_bridge/portal.py`: Matrix ↔ Meta portal logic, including WhatsApp-specific advanced features and generic Messenger/Instagram sends.
- `meta_cloud_bridge/db/upgrade.py`: generic Meta tables and columns: `meta_account`, `portal.remote_user_id`, `portal.account_id`, `message.remote_message_id`, etc.
- `meta_cloud_bridge/db/meta_account.py`: stores `account_id`, `channel`, `asset_id`, `send_asset_id`, `access_token`, and owner/admin metadata.

Coupling risks:

- Some Python compatibility aliases still exist in the WhatsApp-specific code path, but the physical database schema uses generic Meta identifiers.
- `portal` uses `(remote_user_id, account_id)` to model WhatsApp users, Messenger PSIDs, and Instagram IGSIDs.
- `message.remote_message_id` stores provider message IDs across all channels.
- `meta_account` stores channel/account configuration with generic `account_id`, `channel`, `asset_id`, `send_asset_id`, and token fields.

## Recommended technical decision for the MVP

Implement a clean shared “Meta Graph Messaging” layer and support:

1. WhatsApp Cloud API.
2. Messenger via Page Send API.
3. Instagram Messaging via Messenger Platform for Instagram accounts linked to Pages.
4. Instagram Messaging via Instagram Login (`graph.instagram.com`) as a separate mode if full coverage is required.

Because there is no production WhatsApp deployment, we can avoid preserving old database compatibility too aggressively and design a clean multichannel schema from the start.

## Recommended abstraction model

### Concepts

```text
MetaChannel = whatsapp | messenger | instagram | instagram_login
MetaAsset = phone_number | page | instagram_professional_account
RemoteUserID = wa_id | PSID | IGSID
RemoteMessageID = wamid | mid
ConversationKey = (channel, asset_id, remote_user_id)
```

### Outbound client

Create a new package, for example:

```text
meta/
  client.py              # shared HTTP, auth, request/error handling
  types.py               # common enums and dataclasses
  media.py               # upload/download abstraction
  channels/
    whatsapp.py          # WhatsApp adapter
    messenger.py         # Messenger Page API adapter
    instagram.py         # IG via Messenger Platform adapter
    instagram_login.py   # IG Login / graph.instagram.com adapter
  webhook.py             # unified webhook router/parser
```

Suggested interface:

```python
class MetaMessagingClient(Protocol):
    async def send_text(self, conversation, text, reply_to=None) -> SendResult: ...
    async def send_media(self, conversation, media, caption=None, reply_to=None) -> SendResult: ...
    async def send_reaction(self, conversation, message_id, emoji) -> SendResult: ...
    async def mark_read(self, conversation, message_id) -> None: ...
```

### Webhook router

A single `/receive` handler should:

1. Validate `X-Hub-Signature-256` if `app_secret` is configured.
2. Parse JSON.
3. Detect the channel:
   - `object == "whatsapp_business_account"` => WhatsApp.
   - `object == "page"` + `entry[].messaging[]` => Messenger or Instagram Page-linked. Distinguish using configured assets and/or IDs/fields.
   - `object == "instagram"` => Instagram Login mode.
4. Normalize each event into a shared event shape:

```python
@dataclass
class IncomingMessage:
    channel: MetaChannel
    asset_id: str
    sender_id: str
    recipient_id: str
    message_id: str
    timestamp: datetime
    kind: Literal["text", "image", "audio", "video", "file", "location", "reaction", "read", "delivery", "postback", "unsupported"]
    text: str | None
    attachments: list[RemoteAttachment]
    reply_to: str | None
    raw: dict
```

5. Send the normalized event to `Portal` using generic APIs such as `handle_remote_message` instead of `handle_whatsapp_message`.

## Recommended implementation plan

### Phase 0 — baseline and test fixtures

- Add tests/fixtures for current WhatsApp behavior before the refactor.
- Keep the public webhook endpoint unchanged initially (`/cloud/receive`).
- Add real HMAC signature validation over the raw body if it is not already implemented.

### Phase 1 — clean multichannel schema

Because there is no production data, prefer a clean schema over a long compatibility migration.

Proposed core tables:

```sql
CREATE TABLE meta_account (
  id TEXT PRIMARY KEY,
  channel TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  business_id TEXT,
  page_id TEXT,
  ig_user_id TEXT,
  phone_number_id TEXT,
  access_token TEXT NOT NULL,
  app_secret TEXT,
  name TEXT,
  admin_user TEXT,
  UNIQUE(channel, asset_id)
);

CREATE TABLE portal (
  channel TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  remote_user_id TEXT NOT NULL,
  mxid VARCHAR(255),
  relay_user_id VARCHAR(255),
  encrypted BOOLEAN DEFAULT false,
  PRIMARY KEY (channel, asset_id, remote_user_id)
);

CREATE TABLE message (
  event_mxid VARCHAR(255) PRIMARY KEY,
  room_id VARCHAR(255) NOT NULL,
  channel TEXT NOT NULL,
  asset_id TEXT NOT NULL,
  remote_user_id TEXT NOT NULL,
  sender VARCHAR(255) NOT NULL,
  remote_message_id TEXT NOT NULL,
  created_at TIMESTAMP WITH TIME ZONE NOT NULL,
  UNIQUE (event_mxid, room_id),
  UNIQUE (channel, asset_id, remote_message_id)
);
```

### Phase 2 — shared Graph client

- Extract base URL/version/auth/error parsing from `whatsapp/api.py` into `MetaGraphClient`.
- Reimplement `WhatsappClient` as a channel adapter on top of that client.
- Add `MessengerClient`:
  - `send_text`: `POST /{page_id}/messages` with `recipient.id=PSID`, `messaging_type=RESPONSE`.
  - `send_media`: public URL or `/{page_id}/message_attachments`.
  - replies via `reply_to.mid`.
- Add `InstagramMessengerClient`:
  - same endpoint as Messenger with `recipient.id=IGSID`.
  - confirm in sandbox whether `messaging_type` is accepted/required for all payload types.
- Add `InstagramLoginClient` if included:
  - base URL `https://graph.instagram.com`.
  - endpoint `/{ig_id}/messages` or `/me/messages`.

### Phase 3 — multichannel webhook handling

- Rename `WhatsappHandler` to `MetaWebhookHandler` or wrap it.
- Implement parsers:
  - `WhatsAppWebhookParser`
  - `MessengerWebhookParser`
  - `InstagramMessengerWebhookParser`
  - `InstagramLoginWebhookParser`
- Distinguish Messenger vs Instagram Page payloads:
  - ideal: look up `entry.id` in the configured account table by channel.
  - if the same Page serves both Messenger and Instagram, inspect sender/recipient and event-specific fields; validate with real payloads.
- Normalize events and pass them to the portal layer.

### Phase 4 — generic portal/formatter layer

- Change `Portal` concepts:
  - `remote_user_id` for WhatsApp wa_id, Messenger PSID, and Instagram IGSID.
  - `account_id` for the configured Meta channel account.
  - shared Meta Graph client plus channel adapters.
- Keep thin wrappers only where they reduce churn.
- Adapt bridge info/protocol display names per channel.
- Matrix username templates per channel:
  - `wa_{userid}` for WhatsApp.
  - `msgr_{userid}` for Messenger.
  - `ig_{userid}` for Instagram.

### Phase 5 — provisioning/config

- Extend registration API:
  - channel (`whatsapp|messenger|instagram|instagram_login`).
  - asset IDs: `waba_id`, `phone_number_id`, `page_id`, `ig_user_id`.
  - token type: system/user/page/instagram user token.
- Extend `example-config.yaml`:
  - `meta.base_url: https://graph.facebook.com`
  - `meta.instagram_base_url: https://graph.instagram.com`
  - `meta.version: v25.0` or configurable
  - `meta.app_secret`
  - `bridge.channel_templates.*`

### Phase 6 — tests/fixtures

Minimum fixtures:

- WhatsApp inbound text, image, read status, failed status, reaction, edit.
- Messenger inbound text, attachment, echo, read, delivery, postback.
- Instagram inbound text, attachment, seen, postback, reaction, echo via `messages`.
- Instagram Login payloads if supported.
- Valid/invalid HMAC.
- Duplicate event delivery.

## Open questions / sandbox validation required

1. For Page-linked Instagram, confirm whether we always use `/{PAGE_ID}/messages` or `/me/messages`. The docs show both with a Page token.
2. The current README/AGENTS intent mentions `POST graph.facebook.com/{ig_user_id}/messages`. Current docs split this into:
   - Page-linked IG: `graph.facebook.com/{PAGE_ID|me}/messages` with IGSID as recipient.
   - IG Login: `graph.instagram.com/{IG_ID|me}/messages`.
   The intent should be updated or both modes should be explicitly supported.
3. How to reliably distinguish Messenger vs Instagram when both arrive as `object=page` and can share a Page ID. Likely solution: account config + scoped ID/event fields; validate with real payloads.
4. 24-hour messaging windows/tags: Messenger uses `messaging_type`/tags; Instagram has a 24-hour window and Human Agent support; WhatsApp uses the 24-hour customer service window and templates.
5. Matrix-to-Messenger/Instagram media: choose between temporary public homeserver/proxy URLs and `message_attachments` file upload.
6. App Review: prepare screencasts for `pages_messaging`, `instagram_manage_messages`, `whatsapp_business_messaging`, `pages_manage_metadata`.

## Recommended next step

Before implementing new channel features, perform a safe but clean refactor:

1. Introduce `channel` and generic IDs in the models.
2. Create `meta/` with `MetaGraphClient` and a WhatsApp adapter using the current logic.
3. Add fixture tests for current behavior.
4. Implement Messenger and Page-linked Instagram on top of the new abstraction.
5. Add Instagram Login mode if full Instagram coverage is part of the acceptance criteria.
