# QQBot Idle-Bucket Mechanism — Reference

> Deep-dive companion to the `qqbot-websocket-disconnect` skill.
> Audience: on-call engineer who needs to understand *why* cold restart works
> and how to distinguish idle-bucket from app_id risk-control.

## 1. Protocol-level behavior

QQBot WebSocket gateway (as of 2026-Q2) implements a **session-resume** protocol
modeled on Discord's gateway v6. Lifecycle:

```
client → open WebSocket
server → Hello { heartbeat_interval }
client → Identify { token, session_id?, resume_seq? }
        └─ if session_id+resume_seq present → Resume (continue prior session)
        └─ else → fresh Identify (new session)
server → Ready { session_id }
client → heartbeat every N seconds
server → dispatches events with monotonically increasing `s` (seq)
```

The session is identified by `session_id`, **not** by the TCP connection.
A client may disconnect and reconnect minutes later, presenting the same
`session_id` + last seen `seq`, and the server will replay missed events.
This is what makes "resume" work — and what creates the idle bucket problem.

## 2. Idle-bucket implementation (inferred)

Based on observed behavior in production (`code=4006 session_idle_timeout`,
~60s cadence, same `session_id` across resumes):

- Server tracks each `session_id` in an in-memory bucket keyed by
  `(app_id, session_id)`.
- A session enters the **idle bucket** when:
  - The TCP connection drops without an explicit `close` frame **AND**
  - No new resume arrives within the **grace window** (~30s).
- Idle-bucket sessions are kept alive for ~60s of wall time so resume can
  succeed; after that, server replies `4006 session_idle_timeout` on the
  resume attempt and **marks the session as zombie**.
- Zombie sessions are re-checked on every subsequent resume; if the new
  connection stays idle >60s again, the cycle repeats.

### Why "resume success + ~60s kick" is the fingerprint

- `resume_seq` increments → server *accepts* the resume (session is still
  in the bucket).
- ~60s later → connection closes with 4006 (session hits the idle cap).
- The new connection is the *next* resume, which inherits the same zombie
  bucket because `session_id` is unchanged.

Cold restart produces a fresh `session_id` (e.g., `s_8f2a` → `s_b19c`),
which lands in a **new** bucket — the old zombie marker does not apply.

## 3. Distinguishing idle-bucket from app_id risk-control

These two failure modes look identical in errors.log at first glance.
Use the table below to disambiguate:

| Signal                                 | Idle-bucket                              | App_id risk-control                                  |
|----------------------------------------|------------------------------------------|------------------------------------------------------|
| `code`                                 | `4006`                                   | `4006` for ~1-2h, then `4001` / `4004`                |
| `session_id`                           | Same across all cycles                   | Same for first few cycles, then server rotates it    |
| Cadence                                | Exactly ~60s                             | Variable (60s, 90s, 120s...)                         |
| Cold restart fixes it                  | Yes, for at least 24h                    | No — reappears within 1-2h                           |
| `app_id` in gateway_state.json         | Same                                     | Same (server doesn't change app_id from its side)    |
| `client_secret` validity               | Valid                                    | May go invalid partway through (server rotates it)   |

### Decision rule

1. Cold restart → wait 2h → grep `code=4006` count.
2. If 0 over 2h: **idle-bucket**, mark resolved.
3. If >0 but < baseline: residual zombie markers draining; wait another 2h.
4. If ≥ baseline or growing: **app_id risk-control** — go to q.qq.com, reset
   the secret associated with `app_id`, update `~/.hermes/config.yaml`,
   cold restart again.

## 4. Why tweaking heartbeat_interval doesn't help

Heartbeat is sent *within* an active session. The server's idle bucket
counts **wall time since last activity**, and a heartbeat counts as activity
*only if it arrives before the TCP connection drops*. Once the connection
is gone, no heartbeat helps — the server's clock keeps ticking.

Lowering `heartbeat_interval` (e.g., from 30s → 10s) does not delay the
4006 because the close happens *before* the next heartbeat would have been
sent. Raising it makes things worse (server thinks you're idle sooner on
unstable networks).

**Don't touch heartbeat_interval as a fix.**

## 5. When the resume "succeeds" but messages don't flow

A subtle failure mode: `resume_seq` increments, errors.log is silent, but
QQ channel is dead. This is **not** idle-bucket — it's typically:

- `state.db` lock contention (stale handle from a crashed worker).
- An upstream rate-limit on the bot's `app_id` that returns 200 but drops
  messages silently.
- A misrouted dispatch rule in `gateway_state.json` → `platforms.qqbot.routes`.

Check:

```bash
lsof ~/.hermes/state.db | wc -l   # >1 → stale handle
grep -c "dispatch.drop" ~/.hermes/logs/agent.log  # non-zero → rate-limited
```

If any of these match, this skill is **not** the right one — exit and
investigate gateway dispatch layer.

## 6. Forensic template for QQ 开放平台 tickets

When escalating to q.qq.com support, attach:

```
=== gateway_state.json ===
{ "platforms": { "qqbot": { "state": "...", "session_id": "..." } } }

=== errors.log (last 200 lines, 4006 only) ===
{grep output}

=== Cold restart timeline ===
{marker line timestamps + counts}

=== App metadata ===
app_id: {from config.yaml}
client_secret last reset: {date}
```

Support typically responds in 24-72h. While waiting, a workaround is to
**rotate to a new app_id** (different bot registration), which gives you
a fresh bucket — but requires re-authorizing users.

## 7. Related reading

- Discord gateway v6 spec (the protocol QQBot borrows from):
  https://discord.com/developers/docs/topics/gateway
- Hermes gateway_state schema: `~/.hermes/gateway_state.json` (see also
  `gateway_state.schema.json` in the main repo).