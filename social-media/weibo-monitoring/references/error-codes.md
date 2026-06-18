# Weibo Open API — Error Code Reference

Detailed catalog of error codes you will hit when using the Weibo Open API
(`open.weibo.com` / `api.weibo.com/2/...`). The SKILL.md troubleshooting
table covers the common ones; this file is the long-form reference.

Source: Weibo Open Platform docs + observed behavior in production polls
through 2026.

## Error code groups

### Authentication / token errors (1xxxx)

| Code | Message | Meaning | Recovery |
|---|---|---|---|
| 10006 | "User does not exist" | `uid` invalid OR account deleted/suspended | Re-resolve via `ajax/profile/info`; mark account `DEAD` if still 10006 after 3 retries |
| 10009 | "User does not exist" (legacy) | Same as 10006 on older endpoints | Same |
| 10010 | "Domain name error" | Calling endpoint outside approved redirect URI | Re-check app's "安全域名" in the developer console |
| 10020 | "Need permission" | App not approved for this scope | `open.weibo.com/development/...` → apply for `statuses/read` / `friendships/read` |
| 10021 | "Too many apps" | Same user authorized >20 apps | User must revoke one before you can re-auth |
| 10022 | "IP limit" / "Requests too frequent" | Per-IP quota exceeded | Back off 60s; consider proxy pool |
| 10023 | "Appkey does not exist" | Bad `client_id` OR app unpublished | Re-register; check app is in "已上线" state |
| 10024 | "Token expired" | `access_token` past `expires_in` | Re-run OAuth2 flow; for `authorization_code` use refresh token |
| 10025 | "Invalid access_token" | Token revoked OR wrong app | Full re-auth |
| 10026 | "Invalid refresh_token" | Refresh token also expired | Full re-auth from scratch |
| 10027 | "Code expired" | OAuth `code` older than 5 minutes | Restart auth flow — `code` is single-use |
| 10028 | "Invalid redirect_uri" | Mismatch between call and app config | Update app's `redirect_uri` field to exact match |

### Permission errors (2xxxx)

| Code | Message | Meaning | Recovery |
|---|---|---|---|
| 20003 | "System error" | Weibo backend hiccup | Retry with exponential backoff (1s/2s/4s/8s/16s) |
| 20005 | "User has no permission to do this" | Private account OR scope mismatch | Skip; cannot recover programmatically |
| 20006 | "User is blocked" | The app OR the calling user is blocked by target | Mark target as inaccessible; do not retry |
| 20012 | "Out of limit" | Per-day quota, separate from per-hour | Wait until UTC midnight; consider paid tier |
| 20016 | "Need to add whitelist" | Some endpoints require user whitelist | Add UID in app config before calling |
| 20019 | "Repeat content too fast" | Posted identical text recently | User-side problem; not relevant for read API |
| 20020 | "Need vip authority" | Endpoint is paid-tier only | Upgrade app OR use aggregator service |
| 20021 | "Authentication encryption error" | `client_secret` wrong | Check env var, no trailing newline |

### Request format errors (3xxxx)

| Code | Message | Meaning | Recovery |
|---|---|---|---|
| 30001 | "Parameter invalid" | Missing or malformed param | Check parameter name + type; see endpoint spec |
| 30002 | "Parameter too long" | e.g. `screen_name` > 30 chars | Truncate before sending |
| 30003 | "Parameter empty" | Required param missing | Inspect request — this is a code bug, not a transient error |
| 30004 | "Source param error" | `source` / `client_id` not found | Re-check app key |
| 30005 | "Access denied" | App banned from this endpoint | Permanent; cannot recover |
| 30006 | "Access denied" (read) | Endpoint not available for `authorization_code` grant | Switch to `client_credentials` if appropriate |
| 30007 | "IP not in whitelist" | App has IP whitelist, your IP not on it | Add egress IP OR remove whitelist |
| 30008 | "App callback url error" | `redirect_uri` mismatch | Update app config |

### Rate limit / quota headers

Weibo returns these on most `2/` endpoints — always inspect them:

| Header | Meaning |
|---|---|
| `X-RateLimit-Limit` | Calls allowed in window (per IP+user combo) |
| `X-RateLimit-Remaining` | Calls left in current window |
| `X-RateLimit-Reset` | Unix timestamp when window resets |
| `X-Log` | Request ID — ALWAYS log this, quote in bug reports |

Note: not all endpoints expose `X-RateLimit-*`. When headers are missing, fall
back to the documented per-endpoint quotas (see SKILL.md "Rate-limit
guardrails").

## Endpoint-specific notes

### `statuses/user_timeline.json`
- Quota: ~150/hr per IP+user combo (unverified: ~30/hr)
- `count` max 200 per page; `page` starts at 1
- For high-volume accounts, ALWAYS use `since_id` cursoring — never re-poll
  page 1, you'll miss posts and burn quota.

### `statuses/show.json` (single post)
- Quota: ~1000/hr
- Returns `text` truncated at ~140 chars for long posts — for the full body,
  see `longText` handling in SKILL.md edge cases.
- Soft-deleted posts return HTTP 404 with body `{"error": "...", "error_code": 10006}`.

### `friendships/followers.json` / `friendships/friends.json`
- Quota: ~90/hr
- `cursor` param is a Weibo-specific paging token, NOT a numeric offset.
- Some followers list truncation past 5000 — documented Weibo behavior.

### `search/topics.json`
- Quota: ~60/hr
- Returns most recent 20 by default; `count` max 50
- Some topics restricted (`{"result": false, "error_code": 20005}`).

### `comments/show.json`
- Quota: ~150/hr
- Comments themselves can be deleted — same tombstone pattern as posts.

## Grant-type matrix

| Grant type | Token lifetime | Refresh? | Use case |
|---|---|---|---|
| `client_credentials` | ~24h | No | App-only, public data, no per-user context |
| `password` (Resource Owner) | ~30 days | No (re-login) | Legacy; avoid if possible |
| `authorization_code` | ~30 days | Yes (`refresh_token`) | Acting on behalf of a specific user |
| `authorization_code` (mobile) | ~7 days | Yes | Mobile SDK flows |

For a monitoring skill, `client_credentials` is usually sufficient because
you only need READ endpoints (`statuses/read`, `friendships/read`).
Switch to `authorization_code` only if you need to post, like, or follow.

## What this file does NOT cover

- Realtime push (Weibo does not provide webhooks; you must poll).
- Stories (24h ephemeral content) — not on the Open API at all.
- Ads API — separate registration, separate quotas, separate billing.
- International Weibo (`weibointl.api.weibo.com`) — different auth, different
  endpoint paths, often GeoIP-blocked.

For those, fall back to the aggregator-service path mentioned in SKILL.md.
