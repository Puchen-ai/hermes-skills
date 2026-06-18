---
name: cron-web-fetch-fallback
description: When running as a cron job tasked with fetching live web/news content, environmental constraints often block all web-access tools. Use this skill to diagnose quickly and fail gracefully without fabricating content.
---

# Cron Job Web Fetch — Fallback Strategy

## When to use this skill
Any cron-scheduled task that requires fetching **live, real-time content from the public web** (news, prices, social media, RSS feeds, search results). Especially: daily news digests, market data pulls, social media monitoring, webhooks that need to scrape pages.

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

## Related skills
- `ai-news-daily-cron` — the canonical "daily AI news" cron pattern; check whether the failure you're seeing is documented there, and patch it with your findings if not
- `web` toolset subagent delegation — note that the `web` toolset advertised in `delegate_task` does NOT actually provide web search/fetch in current environments
