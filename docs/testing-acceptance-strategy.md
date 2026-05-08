# Testing and Acceptance Strategy for meta-cloud-bridge

Date: 2026-05-07

## Objective

Validate a complete multichannel Matrix ↔ Meta bridge implementation using only official APIs:

- WhatsApp Cloud API
- Facebook Messenger Platform
- Instagram Messaging via Messenger Platform
- Instagram Messaging via Instagram Login (`graph.instagram.com`) if this mode is included in the final scope

Because there is no production WhatsApp deployment, we can prioritize a clean architecture and test plan from scratch instead of preserving legacy data compatibility.

## Testing principle

Split testing into two groups:

1. **Deterministic tests without real Meta access**: fast, reproducible, suitable for CI. These use official/recorded JSON fixtures and mocked Graph API HTTP responses.
2. **Live/sandbox tests against Meta**: validate tokens, webhooks, permissions, 24-hour windows, real IDs, real media, and actual behavior in Meta apps/web clients.

Final acceptance should pass both groups.

## Meta-provided sandboxing and test modes

Meta does not provide one single universal sandbox for all messaging products. The official testing model is a mix of product-specific test assets, app development mode, app roles, and webhook test notifications.

### App Development Mode and app roles

For Meta apps in development, the app can be exercised by people who have a role on the app: Admin, Developer, Tester, or Consumer Tester. Meta's App Roles documentation says these roles can grant permissions and use features while the app is in development. This is the closest shared sandbox mechanism for Messenger and Instagram.

Practical use for this bridge:

- Keep the Meta app in Development Mode while building.
- Add bridge developers and QA accounts as app Admins/Developers/Testers.
- Use real assets controlled by those role accounts: test Pages, linked Instagram professional accounts, and WhatsApp test numbers.
- Move to Live Mode + App Review only when non-role users/customers must use the app.

Official docs:

- App Roles: <https://developers.facebook.com/docs/development/build-and-test/app-roles/>
- Test Users: <https://developers.facebook.com/docs/development/build-and-test/test-users/>
- Webhooks: <https://developers.facebook.com/docs/graph-api/webhooks/>

Important caveat: Meta's Test Users documentation currently says creation of new test users is temporarily unavailable for some apps. Existing test users and app role accounts can still be used where available.

### WhatsApp Cloud API test number

WhatsApp Cloud API has the most explicit product-specific sandbox: the App Dashboard / WhatsApp API setup flow provides a Meta test business phone number, a Phone Number ID, a WABA ID, and a temporary access token for development sends.

Practical use for this bridge:

- Use the Meta-provided test phone number as the WhatsApp sender.
- Add a small set of real WhatsApp recipient phone numbers in the dashboard test recipient list.
- Use this for smoke tests of inbound/outbound text, media, templates, and statuses.
- Treat this as a limited test environment, not production: it is meant for controlled development recipients and temporary tokens.

Official docs:

- Cloud API Get Started: <https://developers.facebook.com/docs/whatsapp/cloud-api/get-started>
- Set up developer assets: <https://developers.facebook.com/docs/whatsapp/cloud-api/guides/set-up-developer-assets>

### Messenger Platform testing

Messenger does not have a separate open sandbox equivalent to the WhatsApp test number. The official approach is:

- Use a Facebook Page controlled by app role accounts.
- Install/connect the app to that Page.
- Use app role users or test users to message the Page while the app is not publicly approved.
- Use Standard Access for role/test users and Advanced Access + App Review for real customers.

The Messenger webhook documentation states that Messenger/Instagram webhook setup requires a Page/Instagram Professional account installation, and that Standard Access is for notifications from people with a role on the app, while Advanced Access is required for customers who do not have a role.

Official docs:

- Messenger Platform Webhooks: <https://developers.facebook.com/docs/messenger-platform/webhooks>
- Messenger Platform Quick Start: <https://developers.facebook.com/docs/messenger-platform/getting-started/quick-start>

### Instagram Messaging via Messenger Platform testing

Instagram Messaging via Messenger Platform is tested through real Instagram professional accounts linked to Pages, not through a generic sandbox.

Practical use for this bridge:

- Create/use an Instagram professional test account.
- Link it to the Facebook Page used for testing.
- Enable Instagram message access for connected tools.
- Get a Page Access Token with `instagram_manage_messages`.
- Use an app role/test Instagram account to initiate DMs.
- Complete App Review and Advanced Access before allowing arbitrary customer DMs.

Official docs:

- Instagram Messaging API: <https://developers.facebook.com/docs/messenger-platform/instagram>
- Instagram Messaging Get Started: <https://developers.facebook.com/docs/messenger-platform/instagram/get-started>
- Messenger/Instagram Webhooks: <https://developers.facebook.com/docs/messenger-platform/webhooks>

### Instagram API with Instagram Login testing

Instagram Login mode is a different API family. It does not require a linked Facebook Page, but it still relies on development-mode/app-role testing and an Instagram professional account.

Practical use for this bridge:

- Create/use an Instagram professional account.
- Authenticate via Instagram Login / Business Login for Instagram.
- Request `instagram_business_basic` and `instagram_business_manage_messages`.
- Use controlled app role/test accounts before App Review.
- Use `graph.instagram.com` endpoints, not Messenger Page endpoints.

Official docs:

- Instagram API with Instagram Login: <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/>
- Instagram API webhooks: <https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/webhooks/>

### Webhook dashboard tests and local cURL tests

Meta webhook docs also support low-level webhook testing without real messages:

- The App Dashboard can send test webhook notifications for subscribed fields.
- Verification can be tested with a `GET` request containing `hub.mode=subscribe`, `hub.verify_token`, and `hub.challenge`.
- Event handling can be tested with local `POST` requests containing sample JSON.
- Meta requires HTTPS with a valid certificate for dashboard/real webhook verification; self-signed certificates are not supported.

This is useful for checking endpoint reachability and parser behavior, but it does not replace live channel tests because dashboard test payloads may not cover all real payload shapes.

## What we need for testing

### Local/dev infrastructure

- A test Matrix homeserver, ideally Synapse in Docker.
- An appservice registration for the bridge.
- A test database, ideally PostgreSQL in Docker; SQLite can be used for unit tests where supported.
- A public HTTPS URL for the bridge webhook:
  - ngrok, cloudflared tunnel, Tailscale Funnel, Caddy with a real domain, etc.
  - Meta does not accept self-signed certificates.
- A publicly reachable bridge endpoint, for example:
  - `https://<public-host>/cloud/receive`
- Test media files within platform limits:
  - JPEG/PNG image < 8MB
  - MP4 video < 25MB
  - MP4/M4A/WAV/AAC audio < 25MB
  - PDF < 25MB
- Configuration and logging rules that prevent tokens or app secrets from being logged.

### Shared Meta requirements

- Meta developer account.
- Meta Business App in Development Mode for testing.
- App ID.
- App Secret.
- Webhook Verify Token.
- Enabled products depending on the channel:
  - WhatsApp
  - Messenger
  - Instagram Messaging
  - Instagram API with Instagram Login, if that variant is supported
- Test users added as app testers/admins/developers.
- For production or external users, App Review, Business Verification, and Advanced Access will be needed. For sandbox acceptance, Development Mode + app roles is enough.

### WhatsApp Cloud API

- Test WABA ID.
- Test Phone Number ID from WhatsApp > API Setup.
- Access token with `whatsapp_business_messaging`.
- Recipient phone number added to the test recipients/allowlist in the Meta dashboard.
- Webhook subscribed to the `messages` field.
- Optional for management webhooks: `whatsapp_business_management`.

### Messenger

- Test Facebook Page.
- Page access token.
- Facebook test user able to send messages to the Page.
- Permissions/tasks:
  - `pages_messaging`
  - `pages_manage_metadata`
  - `pages_show_list`
  - sufficient Page task: MESSAGE/MODERATE/MANAGE depending on the endpoint.
- App installed/subscribed to the Page.
- Recommended webhook fields:
  - `messages`
  - `message_echoes`
  - `message_reads`
  - `message_deliveries`
  - `message_reactions`
  - `messaging_postbacks`
  - `messaging_referrals`
  - `standby`

### Instagram Messaging via Messenger Platform

- Test Instagram Professional account.
- IG account linked to the test Facebook Page.
- Message access for connected tools enabled in Instagram settings.
- Page access token for the linked Page.
- Test IG account/user that initiates a DM conversation.
- Permission:
  - `instagram_manage_messages`
- Usually also needed for onboarding/webhooks:
  - `pages_manage_metadata`
  - `pages_show_list`
- Recommended webhook fields:
  - `messages`
  - `messaging_seen`
  - `message_reactions`
  - `messaging_postbacks`
  - `messaging_referrals`
  - `standby`

### Instagram Messaging via Instagram Login (`graph.instagram.com`)

Only required if this mode is included in the implementation scope.

- Instagram Professional account.
- Instagram User access token.
- Base URL `https://graph.instagram.com`.
- Permissions:
  - `instagram_business_basic`
  - `instagram_business_manage_messages`
- Instagram Messaging webhook subscriptions:
  - `messages`
  - `messaging_optins`
  - `messaging_postbacks`
  - `messaging_reactions`
  - `messaging_referrals`
  - `messaging_seen`

## Test pyramid

### 1. Unit tests / offline contract tests

Suggested tools:

- `pytest`
- `pytest-asyncio`
- `aioresponses` or a fake `aiohttp` server for Graph API mocks
- JSON fixtures in `tests/fixtures/meta/`

Minimum coverage:

- Webhook GET verification:
  - valid verify token returns the challenge.
  - invalid verify token returns 403.
- HMAC signature verification:
  - valid `X-Hub-Signature-256` is accepted.
  - invalid signature is rejected.
  - missing signature behavior is configurable; production mode should reject it.
- Payload parsing:
  - WhatsApp inbound text/media/location/reaction/edit/failed status/read status.
  - Messenger inbound text/media/postback/reaction/read/delivery/echo.
  - Instagram Page-linked inbound text/media/seen/reaction/postback/echo inside `messages`.
  - Instagram Login payloads if supported.
- Normalization:
  - every payload converts into a shared event with `channel`, `asset_id`, `remote_user_id`, `remote_message_id`, `event_type`, `text`, `attachments`, `reply_to`, and `raw`.
- Outbound builders:
  - Matrix text → correct WhatsApp payload.
  - Matrix text → correct Messenger payload.
  - Matrix text → correct Instagram payload.
  - replies → `context.message_id` on WhatsApp and `reply_to.mid` on Messenger/Instagram.
  - media → `id` on WhatsApp, `attachment/url` or `attachment_id` on Messenger/Instagram.
- Idempotency:
  - delivering the same `wamid`/`mid` twice does not create duplicate Matrix messages.
- Graph API errors:
  - invalid token.
  - insufficient permission.
  - 24-hour window closed.
  - rate limit.
  - unsupported media type / media too large.
- DB/migrations:
  - clean schema creates all tables.
  - unique constraints prevent duplicates.
  - because there is no production data, a destructive dev migration is acceptable if it simplifies the schema.

### 2. Offline integration tests

Run the bridge with:

- temporary database.
- fake Matrix client or test double.
- fake Graph API.

Cases:

- Realistic webhook POST → portal is created → fake Matrix event is sent.
- Fake Matrix event → fake Graph API receives the correct payload.
- Fake Matrix media event → fake upload → fake media send.
- Fake Graph API error → Matrix/admin notice is generated.

### 3. Local E2E with a real Matrix homeserver

Recommended stack:

- `docker compose` with Synapse + PostgreSQL + bridge.
- generated appservice registration.
- test Matrix user.

Cases:

- Join/use a portal room created from a fake inbound webhook.
- Send a message from Matrix and observe the fake Graph API request.
- Verify rooms, puppets, display names, and bridge info.
- Verify Matrix media upload/download paths.

### 4. Live sandbox acceptance against Meta

This is manual or semi-automated because real testers usually need to initiate conversations.

For each channel:

1. Register the channel/account in the bridge via provisioning/config.
2. Configure Callback URL and Verify Token in Meta.
3. Confirm GET verification succeeds.
4. Confirm valid POST signature handling.
5. From a remote test user, initiate a conversation.
6. Confirm a Matrix portal appears.
7. Reply from Matrix.
8. Confirm delivery in the remote app/client.
9. Test inbound and outbound media.
10. Test replies/threading.
11. Test read receipts/status/failures where available.
12. Re-deliver the same webhook and confirm no duplicate message is created.

## Functional acceptance criteria

### Common criteria for all channels

- A single webhook endpoint accepts and routes all configured channels correctly.
- HMAC signature verification is enforced in secure mode.
- Duplicate events do not create duplicate Matrix messages.
- Tokens/secrets are not printed in logs.
- Graph API errors are reported to the admin or Matrix room in a clear way.
- Each portal is identified by `(channel, asset_id, remote_user_id)`.
- The bridge stores bidirectional Matrix event ID ↔ remote message ID mappings.
- At minimum, the bridge supports:
  - inbound/outbound text
  - inbound/outbound images
  - inbound/outbound files/PDFs
  - inbound/outbound audio/video where the channel allows it
  - replies/threading
  - read receipts or seen events where exposed by the channel
  - reactions where exposed by the channel
  - fallback for unsupported messages

### WhatsApp

- Inbound WhatsApp text creates/uses the correct Matrix portal.
- Matrix text sends `POST /<phone_number_id>/messages`.
- Matrix media uploads through `/<phone_number_id>/media` and sends by media ID.
- Inbound media downloads through a media URL with bearer token.
- `read` status is reflected in Matrix where possible.
- `failed` status generates a readable notice.
- Replies use `context.message_id`.
- Templates/interactive messages inherited from upstream continue working or are reimplemented in the WhatsApp module.

### Messenger

- Inbound text/media from Messenger Page arrives in Matrix.
- Matrix text sends `/<PAGE_ID|me>/messages` with `recipient.id = PSID`.
- `messaging_type = RESPONSE` is used within the 24-hour window.
- `message_echoes` do not create duplicates.
- `message_reads` / `message_deliveries` are processed.
- Media works via public URL or `message_attachments`.
- Replies use `reply_to.mid`.

### Instagram Page-linked

- Inbound IG DM arrives as `object=page` and routes to the Instagram channel, not Messenger.
- Matrix text sends `/<PAGE_ID|me>/messages` with `recipient.id = IGSID`.
- Instagram echoes included in `messages` do not create duplicates.
- `messaging_seen` is processed.
- Reactions/postbacks are processed.
- Media respects IG limits and works inbound/outbound.

### Instagram Login mode

If included:

- Uses `graph.instagram.com`, not `graph.facebook.com`.
- Uses an Instagram User access token.
- Sends to `/<IG_ID|me>/messages`.
- Instagram webhooks normalize into the same event model.

## Non-functional acceptance criteria

- Respond to webhooks in less than 5 seconds.
- Handle Meta retries without duplicate events.
- Use reasonable timeouts/retries for Graph API calls.
- Rate limits and 5xx errors do not crash the bridge process.
- Database state remains consistent if Matrix send or Graph send fails.
- Configuration is clear for multiple accounts/channels.
- Logs include useful context: `channel`, `asset_id`, `remote_user_id`, `remote_message_id`.
- All offline tests pass in CI without real credentials.

## Suggested environment variables for live tests

Do not commit these. Use `.env.local`, a secret manager, or manual CI secrets.

```bash
META_APP_ID=
META_APP_SECRET=
META_VERIFY_TOKEN=
META_API_VERSION=v25.0
META_PUBLIC_WEBHOOK_URL=https://example.ngrok.app/cloud/receive

WA_ACCESS_TOKEN=
WA_WABA_ID=
WA_PHONE_NUMBER_ID=
WA_TEST_RECIPIENT_PHONE=

FB_PAGE_ID=
FB_PAGE_ACCESS_TOKEN=
FB_TEST_PSID=   # can be captured after the first webhook

IG_PAGE_ID=
IG_PAGE_ACCESS_TOKEN=
IG_TEST_IGSID=  # can be captured after the first webhook

IG_LOGIN_ACCESS_TOKEN=
IG_LOGIN_IG_ID=
IG_LOGIN_TEST_IGSID=
```

## Recommended live acceptance flow

### Precheck

- Bridge starts.
- `/receive` responds to the verify challenge.
- Valid fake HMAC payload is accepted.
- Invalid fake HMAC payload is rejected.
- Bridge can talk to Matrix.

### WhatsApp smoke test

1. Send a WhatsApp message from the tester phone to the Meta test phone number.
2. Confirm a Matrix portal is created.
3. Reply from Matrix.
4. Send an image from WhatsApp; confirm Matrix receives media.
5. Send an image from Matrix; confirm WhatsApp receives media.
6. Re-deliver the same webhook fixture; confirm no duplicate appears.

### Messenger smoke test

1. Send a message from the Facebook test user to the Page.
2. Confirm a Matrix portal is created.
3. Reply from Matrix.
4. Test image/PDF if Messenger allows it.
5. Mark the conversation as read in Messenger and verify the event if delivered.
6. Confirm echoes do not duplicate messages.

### Instagram Page-linked smoke test

1. Send a DM from the IG test account to the IG professional account.
2. Confirm a Matrix portal is created with channel Instagram.
3. Reply from Matrix.
4. Test image/short video.
5. Verify seen/reaction events if delivered.
6. Confirm echoes do not duplicate messages.

### Instagram Login smoke test

Only if this mode is in scope:

1. Authenticate/acquire an IG Login token.
2. Send a DM from the tester.
3. Confirm Instagram webhook and Matrix portal.
4. Reply from Matrix via `graph.instagram.com`.

## Recommended acceptance scope

To consider the base bridge “complete”, accept:

- Stable multichannel core: text, media, replies, reactions/read receipts where available, deduplication, error handling.
- Single webhook with reliable routing.
- Config/provisioning for multiple assets.
- Strong offline tests.
- Live smoke tests for the main three channels.

More channel-specific features can be implemented as follow-up modules, but the architecture should support them:

- WhatsApp templates/flows/catalogs.
- Messenger templates/quick replies/persistent menu/icebreakers.
- Instagram private replies/icebreakers/templates.
- Human Agent / Handover Protocol.
- Utility/marketing messages.
