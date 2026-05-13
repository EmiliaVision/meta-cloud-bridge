# Meta Platform Gotchas & Undocumented Behavior

Date: 2026-05-13

Hard-won lessons from configuring WhatsApp, Messenger, and Instagram channels
on the Meta Developer Platform. These are things that Meta's official
documentation does not explain clearly (or at all).

---

## 1. Three tokens for three channels

A single Meta app requires **three different token types**. No single token
works across all channels.

| Token type | Where to generate | Works with | Prefix |
|---|---|---|---|
| System User token | Business Settings → System Users → Generate Token | WhatsApp (`graph.facebook.com`) | `EAA…` |
| Page Access Token | Messenger API Settings → "Generate" button next to Page | Messenger (`graph.facebook.com`) | `EAA…` |
| Instagram User Token | Instagram API Settings → "Generate token" next to IG account | Instagram (`graph.instagram.com`) | `IGAA…` |

### What happens with the wrong token

| Attempt | Error |
|---|---|
| System User token → Messenger send | `(#210) A page access token is required` |
| System User token → Instagram send | `(#100) No matching user found` (subcode 2018001) |
| Page Access Token → Instagram send | `(#100) No matching user found` (subcode 2018001) — token lacks IG messaging scopes |
| IG User Token (`IGAA…`) → `graph.facebook.com` | `Invalid OAuth access token - Cannot parse access token` (code 190) |
| Page Access Token → `graph.instagram.com` | Does not work; IG API requires IG-scoped tokens |

### How to verify a token's scopes

```bash
# For EAA… tokens (System User or Page):
curl "https://graph.facebook.com/v25.0/debug_token?input_token=<TOKEN>&access_token=<APP_ID>|<APP_SECRET>"
# Check .data.scopes — must include pages_messaging for Messenger,
# or whatsapp_business_messaging for WhatsApp.

# For IGAA… tokens: debug_token may not work. Test directly:
curl "https://graph.instagram.com/v25.0/me?access_token=<IGAA_TOKEN>"
```

---

## 2. Instagram uses a separate App Secret

When you add the Instagram API product to your Meta app, Meta silently
creates a **child Instagram App** with its own ID and secret:

| Field | Where to find |
|---|---|
| Instagram app name | Instagram API Settings → top of page |
| Instagram app ID | Instagram API Settings → top of page (clickable link) |
| Instagram app secret | Instagram API Settings → "Show" button next to secret |

**Instagram webhooks are signed with this Instagram App Secret**, not the
main Meta App Secret from App Settings → Basic. If you validate webhooks
using only the main App Secret, all Instagram webhooks will be rejected
with "invalid signature".

### Where to find each secret

```text
Main App Secret:      App Dashboard → Settings → Basic → App Secret → Show
Instagram App Secret: App Dashboard → Use cases → Instagram API → API setup → Instagram app secret → Show
```

---

## 3. Instagram webhook `object` is `"instagram"`, not `"page"`

Meta documentation implies Page-linked Instagram messaging comes through
the Page webhook (`object: "page"`). **In practice, Instagram webhooks
configured via Instagram API Settings arrive as `object: "instagram"`.**

| Webhook source | `object` value | Signed with |
|---|---|---|
| WhatsApp | `whatsapp_business_account` | Main App Secret |
| Messenger | `page` | Main App Secret |
| Instagram (configured via IG API Settings) | `instagram` | **Instagram App Secret** |

This means your webhook handler must:
1. Accept both `app_secret` and `instagram_app_secret` for signature validation
2. Route `object: "instagram"` payloads to Instagram message handling

---

## 4. Instagram send endpoint is `graph.instagram.com`, not `graph.facebook.com`

| Channel | Send API base URL | Send endpoint | Token type |
|---|---|---|---|
| WhatsApp | `graph.facebook.com` | `/{PHONE_NUMBER_ID}/messages` | System User token |
| Messenger | `graph.facebook.com` | `/{PAGE_ID}/messages` | Page Access Token |
| Instagram | **`graph.instagram.com`** | `/{IG_USER_ID}/messages` | IG User Token (`IGAA…`) |

Using `graph.facebook.com` with an IG User Token returns error 190.
Using `graph.instagram.com` with a Page token returns errors.

### Working Instagram send example

```bash
curl -X POST "https://graph.instagram.com/v25.0/<IG_USER_ID>/messages" \
  -H "Authorization: Bearer IGAA..." \
  -H "Content-Type: application/json" \
  -d '{"recipient":{"id":"<IGSID>"},"message":{"text":"Hello"}}'
```

---

## 5. Page subscription requires a Page token, not a System User token

To subscribe a Facebook Page to receive Messenger webhook events via API:

```bash
# ❌ FAILS with System User token (error 210)
curl -X POST "https://graph.facebook.com/v25.0/{PAGE_ID}/subscribed_apps" \
  -H "Authorization: Bearer <SYSTEM_USER_TOKEN>" \
  -d '{"subscribed_fields":"messages,messaging_postbacks"}'

# ✅ WORKS with Page Access Token
curl -X POST "https://graph.facebook.com/v25.0/{PAGE_ID}/subscribed_apps" \
  -H "Authorization: Bearer <PAGE_ACCESS_TOKEN>" \
  -d '{"subscribed_fields":"messages,messaging_postbacks"}'
```

**Workaround:** Do it via the Meta Dashboard UI instead (Messenger Settings →
Add Subscriptions). The dashboard uses your logged-in session which has
sufficient privileges.

---

## 6. System User: Employee vs Admin

When creating a System User in Business Settings:

- **Employee** role: works immediately, sufficient for all messaging operations.
- **Admin** role: requires a **7-day waiting period** before activation.

Use Employee unless you specifically need Admin-level Business Settings access.

Assign these assets to the System User with **Full Control**:

| Asset | Required for |
|---|---|
| Meta App | All channels |
| WhatsApp Business Account (WABA) | WhatsApp |
| Facebook Page | Messenger |
| Instagram Account | Instagram (partial access is sufficient) |

---

## 7. Live Mode required for Instagram webhooks

| App Mode | WhatsApp webhooks | Messenger webhooks | Instagram webhooks |
|---|---|---|---|
| Development | ✅ Work | ✅ Work (role users only) | ❌ **Do not fire** |
| Live | ✅ Work | ✅ Work | ✅ Work |

Switch to Live Mode before testing Instagram. Publishing to Live Mode does
**not** require completed App Review — it just means the app is "published".

---

## 8. Multiple WhatsApp numbers under one WABA

Two (or more) phone numbers can share the same WABA and the same System
User token. They appear as separate phone numbers in WhatsApp Manager.

**Routing caveat:** When a webhook arrives, the `entry.id` field is the
WABA ID (shared), not the phone number ID. You must match by
`value.metadata.phone_number_id` to route to the correct number. If you
match by WABA ID alone, all messages route to the first configured number.

---

## 9. Registering a real WhatsApp number via API

The Meta Dashboard UI for adding real phone numbers can silently fail.
The API path is more reliable:

```bash
# 1. Request SMS verification code
curl -X POST "https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/request_code" \
  -H "Authorization: Bearer {TOKEN}" \
  -d '{"code_method":"SMS","language":"en_US"}'

# 2. Submit verification code
curl -X POST "https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/verify_code" \
  -H "Authorization: Bearer {TOKEN}" \
  -d '{"code":"123456"}'

# 3. Register for Cloud API
curl -X POST "https://graph.facebook.com/v25.0/{PHONE_NUMBER_ID}/register" \
  -H "Authorization: Bearer {TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"messaging_product":"whatsapp","pin":"123456"}'
```

The `pin` in step 3 is a **two-step verification PIN you choose**, not
the SMS code from step 2. If no PIN was previously set, this sets it.

---

## 10. Instagram "Connected Tools" message access

Even if everything else is configured correctly, Instagram DMs will not
flow through the API unless this setting is enabled **in the Instagram
mobile app**:

```text
Instagram App → Settings → Messages and story replies →
  Message controls → Connected Tools → Allow Access to Messages
```

This is a per-account setting controlled by the Instagram account owner,
not by the Meta Developer Dashboard.

---

## 11. Messenger Page token from Dashboard vs OAuth

There are two ways to get a Page Access Token:

| Method | Where | Lifetime | Scopes |
|---|---|---|---|
| **Messenger Settings → Generate** | App Dashboard → Messenger → Settings → Generate access tokens | ~60 days | `pages_messaging`, `public_profile` |
| **OAuth flow** | Graph API Explorer or custom OAuth | Short-lived (1h), exchangeable to 60-day | Depends on requested scopes |

The Dashboard "Generate" button is simpler but only grants Messenger scopes.
If you need both Messenger and Instagram scopes on one token, use the OAuth
flow and request both permission sets.

---

## 12. Instagram "Generate token" creates a different token type

The Instagram API Settings page has its own "Generate token" button next to
connected Instagram accounts. This generates an **Instagram User Token**
(`IGAA…` prefix) that:

- Works only with `graph.instagram.com`
- Has Instagram-specific scopes (`instagram_business_basic`, `instagram_business_manage_messages`, etc.)
- Cannot be used with `graph.facebook.com`
- Cannot be introspected with `debug_token` using the main App Secret (returns transient errors)

**Do not confuse this with the Messenger "Generate" button**, which produces
a Page Access Token (`EAA…` prefix) for `graph.facebook.com`.

---

## 13. Token expiration

| Token type | Default lifetime | How to extend |
|---|---|---|
| System User token | **Never expires** | Already permanent |
| Page Access Token (from Dashboard) | ~60 days | Regenerate from Dashboard |
| Page Access Token (from OAuth) | 1 hour | Exchange for 60-day long-lived token |
| Instagram User Token (from Dashboard) | ~60 days | Regenerate from Dashboard |
| Instagram User Token (from OAuth) | 1 hour | Exchange via `graph.instagram.com/access_token` |

---

## 14. Error code quick reference

| Error message | Code | Subcode | Cause | Fix |
|---|---|---|---|---|
| Page access token required | 210 | — | System User token used for Page API | Use Page Access Token |
| No matching user found | 100 | 2018001 | Wrong token type or wrong API endpoint for channel | IG: use `IGAA` token + `graph.instagram.com` |
| Application does not have capability | 3 | — | IG token used with `graph.facebook.com` | Use `graph.instagram.com` for IG tokens |
| Invalid OAuth access token | 190 | — | `IGAA…` token on `graph.facebook.com` | IG tokens only work with `graph.instagram.com` |
| Unknown error (status=500, code=1) | 1 | — | Messenger send with wrong token | Use Page Access Token for Messenger |

---

## 15. Webhook field subscriptions by channel

### WhatsApp (via WhatsApp Configuration or API)
```text
messages  ← required for inbound messages
```

### Messenger (via Messenger Settings or API)
```text
messages             ← required
messaging_postbacks  ← for button responses
```

### Instagram (via Instagram API Settings)
```text
messages             ← required for DMs
message_reactions    ← for emoji reactions
messaging_seen       ← for read receipts
messaging_postbacks  ← for button responses
```

Note: Instagram field subscriptions are configured in a **different place**
than Messenger subscriptions, even though both are under the same Meta app.
The Instagram webhook subscription has its own "Verify and save" step in
the Instagram API Settings page.

---

## 16. The "Emilia Bridge-IG" child app

When adding Instagram API to a Meta app, Meta creates a child app visible
only in the Instagram API Settings section. It has:

- Its own Instagram App ID (different from the main App ID)
- Its own Instagram App Secret (different from the main App Secret)
- Its own webhook signing behavior

This child app is **not visible** in your main app list at
developers.facebook.com/apps/. It only appears within the parent app's
Instagram API configuration pages.
