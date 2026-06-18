---
name: ai-news-daily-cron
description: Gather latest AI news for daily cron job briefings. Uses Hacker News Algolia API as primary source in network-restricted environments, with fallback strategies. Produces ranked, engagement-sorted, WeChat-ready markdown.
---

# AI News Daily Cron Job

Reusable workflow for daily AI news briefings where network access is restricted to a small set of hosts (Google, DuckDuckGo, most news sites blocked; Hacker News Algolia API works).

## When to use

- Scheduled/cron task to deliver a daily AI news digest
- Sandbox/network-restricted environment where most web search endpoints are blocked
- Need recent (<24h) AI news ranked by engagement

## Step 1: Probe network reachability

Before relying on any API, test which endpoints work. Don't assume — many sandboxes block all HTTPS except a small allowlist.

```python
import urllib.request, socket
socket.setdefaulttimeout(15)

endpoints = [
    "https://www.google.com",
    "https://api.duckduckgo.com/?q=AI&format=json",
    "https://hn.algolia.com/api/v1/search?query=AI&tags=story&hitsPerPage=5",
    "https://news.ycombinator.com",
]
for ep in endpoints:
    try:
        urllib.request.urlopen(urllib.request.Request(ep, headers={'User-Agent':'Mozilla/5.0'}), timeout=10)
        print(f"OK: {ep}")
    except Exception as e:
        print(f"FAIL: {ep}: {e}")
```

In our env, **only hn.algolia.com works**. Build the rest of the workflow around that.

## Step 2: Query HN Algolia with time + topic filters

The key parameters:
- `query=...` — search terms (use OR-via-multiple-calls since HN Algolia doesn't support OR in one query)
- `tags=story` — exclude comments, jobs, polls
- `numericFilters=created_at_i>{unix_ts}` — strict recency filter (unix seconds, not ms)
- `hitsPerPage` — max is ~1000 but keep ≤ 50 to stay fast

```python
import time
yesterday = int(time.time()) - 86400

# Use multiple narrow queries to cover topic breadth
queries = [
    f"https://hn.algolia.com/api/v1/search?query=OpenAI&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=20",
    f"https://hn.algolia.com/api/v1/search?query=Anthropic&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=20",
    f"https://hn.algolia.com/api/v1/search?query=Claude&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=20",
    f"https://hn.algolia.com/api/v1/search?query=Gemini&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=15",
    f"https://hn.algolia.com/api/v1/search?query=GPT&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=15",
    f"https://hn.algolia.com/api/v1/search?query=LLM&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=20",
    f"https://hn.algolia.com/api/v1/search?query=AI+agent&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=20",
    f"https://hn.algolia.com/api/v1/search?query=Nvidia&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=15",
    f"https://hn.algolia.com/api/v1/search?query=AGI&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=15",
    f"https://hn.algolia.com/api/v1/search?query=AI&tags=story&numericFilters=created_at_i>{yesterday}&hitsPerPage=40",
]
```

## Step 3: Deduplicate + verify recency

HN Algolia's relevance sort can sneak in old high-points stories even with `created_at_i` filter set. **Verify each hit's `created_at_i` client-side** before keeping it.

```python
all_stories = {}
for q in queries:
    data = json.loads(urllib.request.urlopen(urllib.request.Request(q, headers={'User-Agent':'Mozilla/5.0'}), timeout=20).read())
    for hit in data.get('hits', []):
        oid = hit['objectID']
        created = hit.get('created_at_i', 0)
        if oid not in all_stories and created > yesterday:  # double-check
            all_stories[oid] = {
                'id': oid,
                'title': hit['title'],
                'url': hit.get('url') or f"https://news.ycombinator.com/item?id={oid}",
                'points': hit.get('points', 0),
                'num_comments': hit.get('num_comments', 0),
                'created_at': hit.get('created_at', ''),
            }
```

## Step 4: Rank by engagement

Sort by `(points, num_comments)` desc. Stories with 5+ points and 5+ comments are typically "real news" — below that is noise.

```python
ranked = sorted(all_stories.values(), key=lambda x: (x['points'], x['num_comments']), reverse=True)
top = [s for s in ranked if s['points'] >= 5][:10]
```

## Step 5: Format for WeChat

Use emoji-tagged markdown. The auto-delivery system on cron handles sending — don't try to call send_message yourself.

Format template:
```
🤖 **AI 今日要闻** (YYYY年M月D日 星期X)

1. 🔥 [标题](链接)
   1-2 句中文摘要 + 来源 / 互动数据

2. 💥 [标题](链接)
   ...
```

Emoji tier suggestions:
- 🔥 — top engagement / consensus discussion (700+ pts)
- 💥 — major news / strong community reaction (200+ pts)
- 🚀 — new product / launch
- 📊 — analysis / data-driven piece
- 🏛️ — institutional / corporate news
- 🗳️ — politics / regulation
- 📈 — market / business
- 💡 — Show HN / tool release
- 🔬 — research / paper
- ⚠️ — warning / incident

## Pitfalls

- **delegate_task with web toolset may fail** — subagents in restricted envs inherit the same network restrictions. Don't waste iterations on it. Use `execute_code` + `urllib` directly.
- **HN search relevance is broken for time queries** — relevance score uses `points`, so a 2023 story with 5000 points can outrank a 2026 story with 50 points in unsorted results. Always use `numericFilters=created_at_i>...` AND sort client-side.
- **Don't trust the filter alone** — the API sometimes returns stories with `created_at_i` slightly outside the filter window. Verify each hit.
- **`tags=story` is critical** — without it, comments and jobs pollute results.
- **Pre-seed / Show HN noise** — filter `points >= 5` to keep only items with real engagement.
- **Subagent max_iterations** — if delegating, set `max_iterations=10+`; subagents often exit after a single tool call.
- **Network unreachable errors are silent** — `urllib` raises `URLError` with `[Errno 101]`. Catch and continue, don't fail the whole task.

## Verification

After composing the digest:
1. Confirm 5-10 items (not more — quality over quantity)
2. Each item has: title, URL, Chinese summary, source
3. Sorted by engagement tier (top first)
4. Date in header is current local date
5. No `[SILENT]` mixed with content
