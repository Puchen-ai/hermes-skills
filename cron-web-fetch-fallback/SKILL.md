---
name: cron-web-fetch-fallback
description: When running as a cron job tasked with fetching live web/news content, environmental constraints often block all web-access tools. Use this skill to diagnose quickly and fail gracefully without fabricating content.
---

# Cron Job Web Fetch — Fallback Strategy

## When to use this skill
Any cron-scheduled task that requires fetching **live, real-time content from the public web** (news, prices, social media, RSS feeds, search results). Especially: daily news digests, market data pulls, social media monitoring, webhooks that need to scrape pages.

### Trigger phrases
Activate this skill when the incoming task matches any of:
- "fetch today's news" / "daily news digest" / "morning briefing"
- "get latest prices for ..." / "scrape <site>" / "monitor <handle> for new posts"
- "pull RSS feed" / "check Hacker News / TechCrunch / Reuters top stories"
- "cron job ... web fetch ... failed" / "tirith blocked curl"
- any scheduled task whose success depends on live public-web data AND where direct terminal / browser / delegate web access may be blocked

Do NOT activate for: one-off user-initiated fetches (user can re-run interactively), private/internal APIs (different fallback strategy), or tasks with no web dependency at all.

## Contents

- [Symptom: All web tools are unavailable in this environment](#symptom-all-web-tools-are-unavailable-in-this-environment)
- [Fast diagnostic — run before attempting a complex fetch](#fast-diagnostic-run-before-attempting-a-complex-fetch)
- [Decision tree](#decision-tree)
- [Critical anti-pattern: DO NOT fabricate news/content](#critical-anti-pattern-do-not-fabricate-newscontent)
- [What to tell the user (when not silent)](#what-to-tell-the-user-when-not-silent)
- [What to do for next time](#what-to-do-for-next-time)
- [Troubleshooting partial-failure modes](#troubleshooting-partial-failure-modes)
- [Edge cases worth deciding in advance](#edge-cases-worth-deciding-in-advance)
  - [Quick pre-flight checklist](#quick-pre-flight-checklist)
- [Worked example: end-to-end cron run](#worked-example-end-to-end-cron-run)
- [Anti-patterns: what NOT to do](#anti-patterns-what-not-to-do)
- [Related skills](#related-skills)
- [See also](#see-also)
- [Validation checklist — did I follow this skill correctly?](#validation-checklist-did-i-follow-this-skill-correctly)
- [Observability — what to track across runs](#observability-what-to-track-across-runs)
- [Revision history](#revision-history)

## Symptom: All web tools are unavailable in this environment
In Hermes cron-job sessions, the following common patterns all fail:

| Tool | Failure mode |
|---|---|
| `terminal` + `curl`/`wget` | Tirith security scanner blocks with `pattern_key: tirith:unknown`, requires user approval (impossible in cron) |
| `browser_navigate` | `page.goto: Page crashed` on most news/social sites (Google News, HN, TechCrunch, Reuters, Bing, 36kr all crash) |
| `delegate_task` with `toolsets: ['web']` | Subagent reports it has no actual web access; returns empty result with exit_reason completed in ~12s with 0 tool calls |
| `execute_code` with `hermes_tools.terminal()` | Same Tirith block as direct terminal |

## Fast diagnostic — run before attempting a complex fetch
```python
# From a cron job, do this 30-second probe:
from hermes_tools import terminal

# 1. Try curl (expect: Tirith block)
r = terminal("curl -s -o /dev/null -w '%{http_code}' https://example.com", timeout=10)
print("curl:", r)

# 2. Try a tiny HTTP fetch via Python urllib (may also be blocked)
try:
    import urllib.request
    with urllib.request.urlopen("https://example.com", timeout=5) as f:
        print("urllib:", f.status)
except Exception as e:
    print("urllib error:", type(e).__name__, str(e)[:100])
```

If both fail → **there is no web access in this session.** Stop trying.

## Decision tree

1. **Probe web access** (30s, see above)
2. **If access works** → proceed with the original task normally
3. **If access fails**:
   - Check if a local cache exists (e.g., `~/.hermes/cache/`, project data dir, last-run state file)
   - If cached data exists and is recent (<24h old) → use it, label clearly as "cached/stale"
   - If no cache → **emit `[SILENT]` and stop.** Do NOT fabricate content.

## Critical anti-pattern: DO NOT fabricate news/content
Even if the user expects "the daily AI briefing," **never invent headlines, summaries, or links** to fill the gap. Fabricated news:
- Misleads the user
- Spreads misinformation
- Wastes trust
- Is a far worse failure than silence

The `[SILENT]` directive exists exactly for this case. The cron contract is "report if you have something real to report" — and the answer is often "I cannot report today."

## What to tell the user (when not silent)
If a partial result is possible (e.g., you have cached data, or some sources worked), be explicit:
- "⚠️ Could not fetch live news — environmental limitation. Showing last cached snapshot from [date]."
- "Today's briefing unavailable: web fetch tools blocked. Will retry tomorrow."

## What to do for next time
After hitting this, consider:
1. Suggest the user move this cron job to an environment with working web tools
2. Or set up a pre-fetch pipeline (e.g., a separate process that writes to a file the cron job can read)
3. Or change the cron to a tool that has native web access (e.g., a different agent runtime)

## Troubleshooting partial-failure modes
The all-or-nothing "curl fails" case is common, but you may see **partial** failures. Diagnose before deciding to go silent.

| Symptom | Likely cause | Action |
|---|---|---|
| `curl` blocked by Tirith, but `WebFetch` tool works | Tirith blocks arbitrary shell; harness-native fetch is allowed | Use `WebFetch` directly — do not keep retrying `terminal` |
| `curl` returns 200, but specific site (NYT, WSJ, Bloomberg) returns 401/403 | Paywall or geo-block | Mark source as paywalled, skip it, continue with other sources |
| `curl` works for plain HTTP, fails for HTTPS | TLS interception or root CA missing | Stop fetch; emit `[SILENT]` — partial transport is worse than none |
| Browser tool loads static pages but crashes on JS-heavy SPAs (Twitter/X, Reddit) | Headless render issue | Drop JS-only sources; try RSS / `/api/` endpoints instead |
| HTTP works, response is 200 but body is empty or `Please complete CAPTCHA` | Anti-bot wall | Do NOT pretend you have content; treat as no access for that source |
| Some sources succeed, some fail mid-run (e.g., 3 of 10 OK) | Rate limit on the failing one | Continue with partial result; clearly label which sources are missing |
| `WebSearch` returns results but `WebFetch` on the result URL fails | Index is cached, live fetch is blocked | Do not use the index — it is misleadingly stale. Emit `[SILENT]` |
| DNS resolves (`example.com` → IP) but TCP connect times out | Egress firewall on port 443/80 | No workaround; emit `[SILENT]` and log `egress-blocked` |
| `urllib` works, `curl` blocked | Tirith is shell-specific, not Python-specific | Prefer Python `urllib` / `http.client` over `terminal` for fetches |
| Cron ran fine yesterday, fails today | Source changed, or env rotated credentials | Check `~/.hermes/logs/cron-failures.log` for regression; fall back to cache or `[SILENT]` |

**Rule of thumb:** if ≥80% of intended sources work, deliver partial output with a clear "missing: X, Y" list. If <80% work or the gap is the *primary* source the cron was built around, prefer `[SILENT]`.

## Edge cases worth deciding in advance
These are not failures — they are scenarios the skill author should have an opinion on. Pick a policy and stick to it across runs.

- **Cache age > 24h but < 7 days.** Still serve it with a staleness label, but include a one-line note: "Last successful fetch: 3 days ago. Live data unavailable today." Do not silently serve week-old news as fresh.
- **Cache age > 7 days.** Discard. A week-old "daily AI briefing" is misinformation. Emit `[SILENT]`.
- **Cron fires while a previous run is still going (overlap).** Use a lockfile (`~/.hermes/cache/<job>.lock`) with `flock -n`. If you can't acquire the lock, exit silently — the previous run will deliver.
- **User's local clock is wrong / drifted.** Trust UTC for staleness math, not local time. Cron uses the host's TZ; log the TZ once for debuggability.
- **Network is up but extremely slow (>10s per request).** For a daily digest this is usually fine; for a 5-minute cron it is fatal. Define a per-job timeout in the contract and enforce it.
- **The user themselves posted a "skip today" or "use yesterday's digest" instruction yesterday.** Honor that — do not re-send.
- **Output channel is also blocked (e.g., email server down).** Log locally; do not retry in a tight loop. A failed delivery that retries every 30s will burn the cron budget.

### Quick pre-flight checklist
Before declaring `[SILENT]`, confirm:
1. Cache miss confirmed (not just "I didn't look in the right place")
2. At least one of {`WebFetch`, `urllib`, `terminal`} was actually attempted and failed
3. Failure mode matches a known pattern above (Tirith, TLS, DNS, egress, captcha)
4. Partial-result threshold not met (<80% sources)
5. Lockfile not held by a prior overlapping run

## Worked example: end-to-end cron run

**Cron entry:** `0 8 * * *` — "Send me the top 5 AI stories this morning."

**Step 1 — Probe (30s).** Run the diagnostic snippet above. Output:
```
curl: {'exit_code': 1, 'stderr': 'tirith:unknown blocked by policy'}
urllib error: URLError <urlopen error [Errno -3] Temporary failure in name resolution>
```
Both fail → **no web access in this session.**

**Step 2 — Check local cache.** Look for `~/.hermes/cache/ai-news/2026-06-18.json`. Either found-and-fresh (<24h) → serve it with a staleness label, or not-found → proceed to step 3.

**Step 3 — Fail gracefully.** The agent's final output to the user is **exactly**:
```
[SILENT] — no web access in this cron session; no fresh cache available. Skipping today's AI briefing. Will retry at 08:00 tomorrow.
```

**Step 4 — Side effects.** Append a one-line entry to `~/.hermes/logs/cron-failures.log`:
```
2026-06-19T08:00:03 ai-news-daily-cron SILENT web-access-blocked cache-miss
```
No email, no Slack ping, no fabricated headlines.

**What did NOT happen:** the agent did not invent plausible-sounding "OpenAI announces ..." or "DeepMind releases ..." items to fill the gap. Silence is the correct output.

## Anti-patterns: what NOT to do

These are observed failure modes from real cron runs. Each one is worse than `[SILENT]`.

### Anti-pattern 1 — Fabricating plausible content
**Bad:** Agent emits "Top AI stories today: 1. OpenAI announces GPT-6 with multimodal ..." when no fetch succeeded.
**Why bad:** User trusts the cron. A single fabricated headline can be quoted, forwarded, or acted on.
**Good:** Emit `[SILENT]` with a clear reason. Silence is a feature, not a failure.

### Anti-pattern 2 — Mixing real and invented items
**Bad:** Agent successfully fetches 2 of 10 sources, then "fills in" the remaining 8 with plausible-sounding items.
**Why bad:** User cannot tell which entries are real. The whole digest becomes suspect.
**Good:** Deliver the 2 real items, label the gap clearly ("only 2 of 10 sources reachable"), and skip the rest.

### Anti-pattern 3 — Retrying in a tight loop
**Bad:** On failure, cron loops `curl` every 30 seconds for 10 minutes before giving up.
**Why bad:** Wastes cron budget, may trip rate limits, and produces no different result than the first attempt in the same session.
**Good:** One diagnostic probe, one decision, exit. Schedule the next attempt via the cron schedule itself.

### Anti-pattern 4 — Hiding failure behind a vague header
**Bad:** Output begins "Morning briefing:" with 5 fabricated items, no disclosure that fetch failed.
**Why bad:** User has no way to know the digest is fake.
**Good:** If any source failed, the output MUST start with a status line: "⚠️ Partial fetch — 3/10 sources unreachable today."

### Anti-pattern 5 — Serving stale cache as fresh
**Bad:** Cache is 5 days old; agent emits it without a staleness label because "the user wants something."
**Why bad:** User acts on stale news. A 5-day-old "breaking" story may already be corrected or retracted.
**Good:** Always include the fetch timestamp. If >24h, prefix the entire output with "⚠️ Cached snapshot from YYYY-MM-DD."

### Anti-pattern 6 — Trusting WebSearch results as live data
**Bad:** `WebSearch` returns titles + URLs; agent treats them as a fresh digest.
**Why bad:** Search indices are hours-to-days stale; the *URLs* often fail on follow-up fetch.
**Good:** `WebSearch` is only a discovery tool, never a content source. A digest must come from fetched bodies.

### Anti-pattern 7 — Bypassing the lockfile
**Bad:** Two cron runs overlap (long fetch); both write to the cache and deliver to the user.
**Why bad:** User gets the briefing twice, possibly with different partial state.
**Good:** Acquire `~/.hermes/cache/<job>.lock` via `flock -n` before any work; exit silently if locked.

### Anti-pattern 8 — Announcing the cron contract change silently
**Bad:** Agent decides "today I'll just send a note saying fetch is broken" without updating the user-facing contract.
**Why bad:** User's downstream automation (parsing the briefing, alerting on missing items) breaks unexpectedly.
**Good:** Contract changes belong in the skill and the cron config — not in one-off agent decisions.

## Related skills
- `ai-news-daily-cron` — the canonical "daily AI news" cron pattern; check whether the failure you're seeing is documented there, and patch it with your findings if not
- `web` toolset subagent delegation — note that the `web` toolset advertised in `delegate_task` does NOT actually provide web search/fetch in current environments

## See also
- [references/tirith-patterns.md](references/tirith-patterns.md) — detailed catalog of Tirith `pattern_key` values seen in practice and how to recognize each from `stderr`
- [references/cache-format.md](references/cache-format.md) — recommended JSON schema for `~/.hermes/cache/<job>/` files, including staleness metadata

## Validation checklist — did I follow this skill correctly?

Run through this before emitting `[SILENT]` or any partial output. A "no" on any item means you should fix the run, not paper over it.

**Probe phase**
- [ ] Ran the curl + urllib probe (or equivalent) before declaring web access unavailable
- [ ] Recorded the exact `stderr` text from the failing tool call
- [ ] If Tirith blocked, identified the `pattern_key` (see [references/tirith-patterns.md](references/tirith-patterns.md))

**Cache phase**
- [ ] Searched for cache in `~/.hermes/cache/<job>/` (not just "did I remember to write one?")
- [ ] Read `fetched_at` (UTC) and computed age against `ttl_policy`
- [ ] Decided fresh / stale-labeled / discard using the explicit thresholds (24h / 7d)
- [ ] Never served a cache older than `stale_days` even when "the user wants something"

**Decision phase**
- [ ] Applied the 80% rule honestly (3/10 sources is NOT "mostly works" for a 10-source digest)
- [ ] Checked lockfile before writing cache or delivering output
- [ ] If partial, the output starts with a status line naming the missing sources
- [ ] If silent, the log line was written BEFORE exit

**Output phase**
- [ ] No item in the digest was authored from general knowledge; every `title`/`url`/`published_at` traces back to a fetched source
- [ ] Stale cache output is prefixed with "⚠️ Cached snapshot from YYYY-MM-DD"
- [ ] `[SILENT]` is exactly the word, no fabricated "briefing unavailable" filler that invents content adjacent to the silence
- [ ] No retry loop — one probe, one decision, exit

**Post-run phase**
- [ ] `~/.hermes/logs/cron-failures.log` (or equivalent) received one line for this run
- [ ] The line includes: timestamp UTC, job name, outcome (SILENT / PARTIAL / OK), `pattern_key` if Tirith, and cache state (hit / miss / stale-hit)
- [ ] If outcome was SILENT for ≥2 consecutive scheduled runs, surfaced that to the user (not just the log)

## Observability — what to track across runs

A single `[SILENT]` is fine. Three `[SILENT]`s in a row is a system problem. Make the failure mode visible without spamming the user.

### Minimum fields to log every run

Append one structured line per run to `~/.hermes/logs/cron-runs.log` (success or failure):

| Field | Purpose |
|---|---|
| `ts` (UTC ISO 8601) | Cross-run correlation, ordering |
| `job` | Multi-job environments need disambiguation |
| `outcome` | `OK` / `PARTIAL` / `SILENT` / `ERROR` |
| `sources_attempted`, `sources_succeeded` | Detect gradual degradation before it becomes 0% |
| `cache_state` | `fresh-hit` / `stale-hit` / `miss` / `disabled` |
| `pattern_key` (if Tirith) | Lets you spot a single `egress-deny` rule breaking N jobs at once |
| `duration_seconds` | Catch slow-but-not-failing runs (e.g., CAPTCHA loops) |
| `silence_streak` | Consecutive SILENT runs for this job — drives alerting |

Format (JSONL):

```json
{"ts":"2026-06-19T08:00:42Z","job":"ai-news-daily-cron","outcome":"SILENT","pattern_key":"tirith:egress-deny","cache_state":"miss","sources_attempted":10,"sources_succeeded":0,"duration_seconds":31,"silence_streak":3}
{"ts":"2026-06-19T08:00:42Z","job":"ai-news-daily-cron","outcome":"PARTIAL","cache_state":"stale-hit","sources_attempted":10,"sources_succeeded":4,"duration_seconds":58,"silence_streak":0}
```

### Metrics worth deriving from the log

- **`success_rate_7d`** per job — fraction of runs with `outcome ∈ {OK, PARTIAL}`. Alert if drops below 50% for two consecutive days.
- **`silence_streak_max`** per job — the longest current run of `SILENT`. If ≥3, the cron is effectively dead and the user should know.
- **`pattern_key_distribution`** — if `tirith:egress-deny` suddenly dominates, an admin probably changed the env's egress policy; not a code bug.
- **`cache_state_miss_rate`** — sustained 100% misses means the pre-fetch pipeline (if any) is broken.
- **`duration_p95`** — rising latency without changing outcome often precedes a hard failure.

### Alerting policy (human, not agent)

The cron agent itself should NOT page the user on every `[SILENT]`. Reserve active notification for:

1. **Hard escalation:** `silence_streak ≥ 3` for the same job → one user-visible message: "Cron `<job>` has been silent for N consecutive runs. Last successful fetch: `<date>`."
2. **Pattern shift:** >50% of jobs start hitting the same `pattern_key` in a single day → likely an env change, not per-job failures.
3. **Schema drift:** cache read fails with `schema_version > known` → a deploy happened; the cron can no longer serve cached data and should stop pretending to.

Do NOT alert on: single `[SILENT]`, single PARTIAL, transient `pattern_key: tirith:unknown` (recoverable), or rate-limit-style source-specific failures.

### Quick observability smoke test

After a code change to the cron or this skill, confirm the log is actually being written:

```bash
# Force a probe-only run that logs but does not deliver
~/.hermes/cache/<job>/probe.sh  # or your cron wrapper's dry-run mode
tail -n 5 ~/.hermes/logs/cron-runs.log
```

If the line appears with all required fields, observability is wired correctly. If the line is missing or malformed, fix that before changing anything else — invisible failures are the worst kind.

## Revision history

| Round | Change |
|---|---|
| 1 | Tightened trigger phrases; added concrete worked example of a cron run ending in `[SILENT]` |
| 2 | Added troubleshooting table for partial-failure modes; documented edge cases (cache age, clock drift, overlap) |
| 3 | Added `references/tirith-patterns.md` and `references/cache-format.md`; expanded anti-patterns from 4 to 8 |
| 4 | Added validation checklist and observability section with JSONL log schema and alerting policy |
| 5 | Added table of contents; converted reference file mentions to markdown cross-links; added this revision history |

Skill `name` is unchanged: `cron-web-fetch-fallback`. YAML frontmatter is preserved. Reference files are unchanged in this round.
