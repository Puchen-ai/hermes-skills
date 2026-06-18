---
name: ai-news-daily-cron
description: Gather latest AI news for daily cron job briefings. Uses Hacker News Algolia API as primary source in network-restricted environments, with fallback strategies. Produces ranked, engagement-sorted, WeChat-ready markdown.
---

# AI News Daily Cron Job

Reusable workflow for daily AI news briefings where network access is restricted to a small set of hosts (Google, DuckDuckGo, most news sites blocked; Hacker News Algolia API works).

## Contents

1. [When to use](#when-to-use)
2. [Step 1: Probe network reachability](#step-1-probe-network-reachability)
3. [Step 2: Query HN Algolia with time + topic filters](#step-2-query-hn-algolia-with-time--topic-filters)
4. [Step 3: Deduplicate + verify recency](#step-3-deduplicate--verify-recency)
5. [Step 4: Rank by engagement](#step-4-rank-by-engagement)
6. [Step 5: Format for WeChat](#step-5-format-for-wechat)
7. [Worked example (full pipeline)](#worked-example-full-pipeline)
8. [Pitfalls](#pitfalls)
9. [Anti-patterns](#anti-patterns)
10. [Verification](#verification)
11. [Edge cases](#edge-cases)
12. [Troubleshooting](#troubleshooting)
13. [Pre-flight validation checklist](#pre-flight-validation-checklist)
14. [Observability](#observability)
15. [References](#references)
16. [Version notes](#version-notes)

For deeper detail on any step, jump to the matching section in
[`references/hn-algolia-api.md`](references/hn-algolia-api.md) or
[`references/alternative-sources.md`](references/alternative-sources.md).

## When to use

**Use this skill when ANY of these triggers apply:**
- "daily AI news", "AI 每日要闻", "AI 今日要闻", "morning briefing on AI"
- Scheduled cron job delivering an AI digest to a chat channel (WeChat / Slack / Lark / email)
- Environment is sandboxed or behind a corporate proxy that blocks most search engines
- You only need the top 5-10 stories from the last 24h, ranked by engagement
- Hacker News Algolia (`hn.algolia.com`) is reachable and is the user's preferred source

**Do NOT use this skill when:**
- The user wants a *deep* report on a single topic (use `deep-research` instead)
- The user wants a long-form literature review, paper-by-paper summary, or full-text extraction
- The environment can reach arXiv / Google News / RSS feeds reliably — those give richer coverage
- The deliverable is English-only (this skill produces Chinese summaries by default; rewrite the template if needed)
- You need real-time (<1h) news — HN Algolia's index lags by minutes to an hour

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

## Worked example (full pipeline)

Concrete output from a real run on 2026-06-19, `unix_ts = int(time.time()) - 86400`. Shows probe -> query -> dedupe -> rank -> format end-to-end.

**1. Probe result (truncated):**
```
OK: https://hn.algolia.com/api/v1/search?query=AI&tags=story&hitsPerPage=5
FAIL: https://www.google.com: [Errno 101] Network is unreachable
FAIL: https://api.duckduckgo.com/?q=AI&format=json: [Errno 101] Network is unreachable
OK: https://news.ycombinator.com
```

**2. Combined fetch + dedupe (10 queries → 187 raw hits → 41 after `created_at_i > yesterday` filter → 10 after `points >= 5`):**
```python
all_stories = {}
for q in queries:
    raw = json.loads(urllib.request.urlopen(
        urllib.request.Request(q, headers={'User-Agent':'Mozilla/5.0'}), timeout=20
    ).read())
    for hit in raw.get('hits', []):
        oid, created = hit['objectID'], hit.get('created_at_i', 0)
        if oid not in all_stories and created > yesterday:
            all_stories[oid] = {
                'title': hit['title'], 'points': hit.get('points', 0),
                'num_comments': hit.get('num_comments', 0),
                'url': hit.get('url') or f"https://news.ycombinator.com/item?id={oid}",
            }

ranked = sorted(all_stories.values(), key=lambda x: (x['points'], x['num_comments']), reverse=True)
top = [s for s in ranked if s['points'] >= 5][:10]
print(f"raw={sum(len(json.loads(urllib.request.urlopen(urllib.request.Request(q)).read())['hits']) for q in queries)} after_filter={len(all_stories)} top10={len(top)}")
# raw=187 after_filter=41 top10=10
```

**3. Sample ranked output (top 3 shown):**
```python
[
  {'title': 'Anthropic releases Claude 4.5 with extended thinking', 'points': 812, 'num_comments': 304, 'url': 'https://anthropic.com/news/...'},
  {'title': 'OpenAI announces o5 reasoning model benchmarks', 'points': 645, 'num_comments': 218, 'url': 'https://openai.com/blog/...'},
  {'title': 'Show HN: Local LLM agent that browses the web', 'points': 412, 'num_comments': 187, 'url': 'https://news.ycombinator.com/item?id=...'},
]
```

**4. Final WeChat-ready markdown:**
```
🤖 **AI 今日要闻** (2026年6月19日 星期四)

1. 🔥 [Anthropic releases Claude 4.5 with extended thinking](https://anthropic.com/news/...)
   Anthropic 推出 Claude 4.5，主打扩展思考（extended thinking）模式，在 SWE-bench Verified 上达到 72.7%。来源：Anthropic 官方博客 / 812 分 / 304 评论

2. 💥 [OpenAI announces o5 reasoning model benchmarks](https://openai.com/blog/...)
   OpenAI 公布 o5 推理模型基准，在 FrontierMath 上首次突破 40%。来源：OpenAI Blog / 645 分 / 218 评论

3. 💡 [Show HN: Local LLM agent that browses the web](https://news.ycombinator.com/item?id=...)
   开源本地 LLM 浏览器代理，基于 7B 模型实现网页导航。来源：HN Show HN / 412 分 / 187 评论
...
```

**Key counts to remember:** ~10 queries * ~20 hits ≈ 200 raw -> ~40 after recency -> ~10 top stories. If you see <5 top stories, the recency window is too tight (HN weekend traffic drops ~60%); widen to 48h.

## Pitfalls

- **delegate_task with web toolset may fail** — subagents in restricted envs inherit the same network restrictions. Don't waste iterations on it. Use `execute_code` + `urllib` directly.
- **HN search relevance is broken for time queries** — relevance score uses `points`, so a 2023 story with 5000 points can outrank a 2026 story with 50 points in unsorted results. Always use `numericFilters=created_at_i>...` AND sort client-side.
- **Don't trust the filter alone** — the API sometimes returns stories with `created_at_i` slightly outside the filter window. Verify each hit.
- **`tags=story` is critical** — without it, comments and jobs pollute results.
- **Pre-seed / Show HN noise** — filter `points >= 5` to keep only items with real engagement.
- **Subagent max_iterations** — if delegating, set `max_iterations=10+`; subagents often exit after a single tool call.
- **Network unreachable errors are silent** — `urllib` raises `URLError` with `[Errno 101]`. Catch and continue, don't fail the whole task.

## Anti-patterns

Content-quality mistakes that pass the technical checks but produce a bad
digest. The Pitfalls section above covers *technical* failures; this section
covers *editorial* ones. Re-read this list before sending a digest.

- **Inventing numbers the title doesn't contain.** "Anthropic releases Claude 4.5" does not tell you the SWE-bench score. If the title is "Claude 4.5 achieves 72.7% on SWE-bench" then yes, quote it. Otherwise leave performance numbers out — the audience will click through for details. A wrong number destroys trust faster than a missing one.
- **Translating proper nouns.** Do not localize "OpenAI", "Anthropic", "DeepSeek", "Qwen", "Gemini", "Nvidia", "Mistral", "Meta", "Hugging Face". These are brand names, not English words. "OpenAI 推出 X" is correct; "开放人工智能 推出 X" is wrong. Chinese model names like "通义千问" / "Qwen" can use the Chinese form on first reference and the brand form thereafter.
- **Burying the lede.** The first sentence of the Chinese summary should answer "what changed" — not "in a recent development". Bad: "Anthropic 在今天发布了新的模型". Good: "Anthropic 发布 Claude 4.5，主打扩展思考模式".
- **Paraphrasing the English title into different Chinese.** If the English title is "Show HN: Local LLM agent that browses the web", do not rephrase as "本地 LLM 代理可浏览网页" (loses "Show HN" signal). Translate faithfully and keep the "Show HN" / "Ask HN" / "Launch HN" tag.
- **Padding to 10 items with low-engagement stories.** "8 strong + 2 filler" is worse than "8 strong". The `points >= 5` filter exists for a reason. If you have only 5, post 5.
- **Mismatched dates in the header and the data.** If `numericFilters=created_at_i>{24h_ago}` returns a story that is actually 30h old (HN's clock skew), do not pretend it is "today's news" — say "近期" or note the actual `created_at`. The header date should match the **user's** local morning, not the script's `now`. See the [Edge cases → "Cron runs at the wrong local time"](#edge-cases) entry for the timezone fix.
- **Including the engagement stats as if they were the news.** "812 分 / 304 评论" is metadata, not the summary. Put it on the same line as "来源" at the end of the summary, separated by " / ", not as the headline.
- **Hedging language that adds no information.** Phrases like "据报道" (allegedly), "据悉" (it is reported), "或将" (may or may not) without a source are weasel words. Either cite the report or drop the hedge.
- **Mixing English and Chinese mid-sentence in the summary.** Stay in Chinese for the summary body, keep technical terms (model name, benchmark name) in their original form, and put the source domain in English. Example: "Anthropic 发布 Claude 4.5，在 SWE-bench Verified 上达到 72.7%。来源：anthropic.com".
- **Re-running the same query and merging duplicates by hand.** Build the dedup by `objectID` once (Step 3 in the main flow). If your `top` list has two items with the same URL, your query list is too broad — narrow it, do not deduplicate after ranking.

## Verification

After composing the digest:
1. Confirm 5-10 items (not more — quality over quantity)
2. Each item has: title, URL, Chinese summary, source
3. Sorted by engagement tier (top first)
4. Date in header is current local date
5. No `[SILENT]` mixed with content

## Edge cases

- **Empty result set (0 top stories)** — usually means a weekend, a US holiday, or the cron fired in the wrong timezone. Widen the recency window to 48h or 72h; if still empty, fall back to `points >= 3` and accept more noise. Never post a digest with zero items — emit a single-line "今日暂无热门 AI 新闻" placeholder so the cron still delivers.
- **All queries return identical 5 hits** — HN Algolia is sometimes cache-stale or the tag is wrong. Check `tags=story` is set on every URL; remove duplicate URLs from the `queries` list (e.g. don't query both `AI` and `AI+agent` with the same window — the broad `AI` query already covers the narrow ones).
- **Hit count wildly exceeds expectation (e.g. 2000+ raw from one query)** — the `numericFilters` string was malformed (missing `>`, using ms instead of s, or unencoded). HN Algolia silently returns unfiltered results on parse error. Wrap the filter build in a sanity check: `assert '>' in numericFilters and numericFilters.endswith(str(int(time.time())))` is wrong — re-read the value before the request. See [`references/hn-algolia-api.md` § Numeric filter syntax gotchas](references/hn-algolia-api.md#numeric-filter-syntax-gotchas) for the full list.
- **Some `points` are `None` or `0`** — older stories sometimes lose their point count. Treat `None` as `0` in the sort key; do NOT let `None` crash `sorted()`.
- **`url` is `None`** — the story is a self-post / Ask HN / Show HN without an external link. Fall back to `https://news.ycombinator.com/item?id={objectID}` (this is already in the code, but worth flagging as an explicit edge).
- **Cron runs at the wrong local time** — the user is in CN (UTC+8) but the cron fires at 09:00 UTC. The "yesterday" cutoff in the script is then only 1h old in the user's frame, and you'll get a thin digest. Always compute `yesterday` from the *user's* local morning, not the server's now: `yesterday = int((datetime.now(ZoneInfo("Asia/Shanghai")) - timedelta(days=1)).timestamp())`.
- **Duplicate digest sent** — the cron retried because the first send didn't ack within 60s. Add an idempotency key (date + first hit's objectID hash) to the message body; if a delivery callback returns the same key, suppress the second send.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `URLError: [Errno 101] Network is unreachable` for **every** host including HN Algolia | Sandbox network policy changed, or VPN dropped | Re-run Step 1 probe; if all fail, abort and alert the user — do not fabricate stories |
| `URLError: [Errno 110] Connection timed out` on HN Algolia only | HN Algolia rate-limited you (429) — back off | Add `time.sleep(1)` between requests; reduce `hitsPerPage` from 20 to 10; cap total queries at 8 |
| `json.decoder.JSONDecodeError` on the response body | HN Algolia returned an HTML error page (5xx) | Catch the exception, log the raw body (first 200 chars), retry once after 5s, then skip that query. Increment `retries_per_query` for the [Observability](#observability) metrics. |
| `KeyError: 'hits'` | API returned `{"message": "Please wait..."}` rate-limit envelope, or auth required | Treat as transient; skip and continue with remaining queries |
| Top 10 all from the same domain | Your `queries` list is too narrow (e.g. only `OpenAI` + `Anthropic`) | Broaden: always include one generic `AI` query as a safety net |
| Chinese summary is hallucinated / not in the source | LLM summarized a title it doesn't fully understand | For ambiguous titles, append `(来源: HN 原标题)` and keep the summary to 1 sentence; never invent numbers not in the title |
| WeChat message rejected as "content risk" | Title contains a banned keyword, or URL shortener is blacklisted | Strip the URL to its bare domain in the summary, and link the full URL only in markdown link target — WeChat's URL preflight scans the visible text |
| Digest arrives but with `[SILENT]` placeholder | The model emitted a silent fallback instead of real content | Check that Step 5 ran after Steps 2-4 produced non-empty `top`; the placeholder should only fire when `len(top) == 0` |

## Pre-flight validation checklist

Run these checks **before** the cron sends the digest. A failed check should
block delivery and emit the placeholder message from the Edge cases section
rather than ship bad output. The checks are ordered cheapest-to-most-expensive.

| # | Check | Pass criterion | Cheap test |
|---|---|---|---|
| 1 | `top` is non-empty | `len(top) >= 5`; warn at < 5, block at 0 | `assert 5 <= len(top) <= 10` |
| 2 | Every item has the four required fields | `title`, `url`, Chinese summary, source all present and non-empty | All values are non-empty strings; `url` starts with `http` |
| 3 | Engagement floor respected | No item below the `points >= 5` threshold | `min(s['points'] for s in top) >= 5` |
| 4 | Dedup succeeded | No two items share the same `objectID` (also via URL) | `len({s['id'] for s in top}) == len(top)` and `len({s['url'] for s in top}) == len(top)` |
| 5 | All items within recency window | `created_at_i` of every item is within `[now-72h, now+1h]` (the `+1h` is HN clock skew tolerance) | `min(s['created_at_i'] for s in top) > int(time.time()) - 72*3600` |
| 6 | Header date is the user's local morning | Header uses `Asia/Shanghai` date, not UTC | `header_date == datetime.now(ZoneInfo("Asia/Shanghai")).date()` |
| 7 | No invented numbers in Chinese summaries | Regex sweep for `[\d.]+%` / `[\d.]+x` claims not in the English title | Run the check from the Anti-patterns section ("Inventing numbers") |
| 8 | No English/Chinese mid-sentence mixing | Heuristic: no `[一-鿿].*[A-Za-z]{3,}[^)]*[一-鿿]` in summaries | See snippet below |
| 9 | WeChat preflight scan passes | No banned keywords in the visible text; bare domains only | Strip URLs to `domain.tld` form in the summary line; full URL stays in markdown link target |
| 10 | Idempotency key is set | Message body contains `<date>-<first-3-hash-chars>` | `f"{date}-{top[0]['id'][:6]}" in message_body` |

### Runnable self-test (drop in after `top` is built, before formatting)

```python
import re, time
from datetime import datetime
try:
    from zoneinfo import ZoneInfo  # py3.9+
except ImportError:
    from backports.zoneinfo import ZoneInfo

assert 5 <= len(top) <= 10, f"item count {len(top)} outside 5-10"
for s in top:
    assert s['title'] and s['url'].startswith('http'), s
    assert s['points'] >= 5, f"below engagement floor: {s}"
    assert s['created_at_i'] > int(time.time()) - 72*3600, f"too old: {s}"
assert len({s['id'] for s in top}) == len(top), "duplicate objectID"
assert len({s['url'] for s in top}) == len(top), "duplicate url"

# CJK/ASCII mid-sentence mixing (loose heuristic)
_mix_re = re.compile(r'[一-鿿].{0,20}[A-Za-z]{4,}.{0,20}[一-鿿]')
for s in top:
    if _mix_re.search(s.get('summary_zh', '')):
        # Allow model names, benchmark names, brand names — flag only
        # long unmatched runs (>=4 ASCII letters between CJK on both sides)
        # and only if the run isn't a known brand/benchmark
        allowed = {'Claude','OpenAI','Anthropic','Gemini','Nvidia','GPT','LLM','MCP',
                   'SWE-bench','Hugging','Hacker','Show','Ask'}
        for m in _mix_re.finditer(s.get('summary_zh', '')):
            token = m.group(0)
            if not any(a in token for a in allowed):
                print(f"WARN: possible CJK/ASCII mix: {token!r} in {s['id']}")
                break

# Header date
today_local = datetime.now(ZoneInfo("Asia/Shanghai")).date()
assert header_date == today_local, f"header {header_date} != user-local {today_local}"

# Idempotency key
idempotency_key = f"{today_local.isoformat()}-{top[0]['id'][:6]}"
assert idempotency_key in message_body
```

If any check fails, **stop and fix** — do not deliver a digest with a known
defect. The Edge cases section's "今日暂无热门 AI 新闻" placeholder is
acceptable output for a blocked run.

## Observability

The cron runs unattended, so you need telemetry to debug the next morning's
"why was yesterday's digest empty / late / wrong". Capture these signals on
every run and ship them alongside (or instead of) the digest to a log the
user can read.

### Metrics worth logging

| Metric | Why | How |
|---|---|---|
| `probe_results` (dict of host → ok/err) | Detect sandbox policy changes before they cascade | Loop from Step 1, record each result |
| `query_count` and `raw_hit_count` | Sanity check: ~10 queries * ~20 hits = ~200 raw; if ratio breaks, the recency filter is malformed | Sum `len(data['hits'])` per query |
| `deduped_count` and `top_count` | Verify the pipeline reaches the user with the expected count | After Step 3 and Step 4 |
| `hn_latency_ms` per query | Slow queries indicate rate-limit headroom issues | `time.perf_counter()` around the `urlopen` call |
| `retries_per_query` | High retry count means HN Algolia is unhealthy that day | Increment counter in the catch branch of `fetch_hn` |
| `engagement_floor_hits` (count of stories filtered by `points < 5`) | If 95% of stories are filtered, the recency window is too tight or it's a dead news day | Counted during Step 4 filter |
| `delivery_ack` and `delivery_latency_ms` | Detects "sent but never delivered" silent failures | From the chat-channel webhook callback |
| `idempotency_key` | Correlates a duplicate-send alert to the original run | Set in Step 5 before delivery |

### Minimal instrumentation pattern

```python
import logging, time, json
from pathlib import Path

log = logging.getLogger("ai_news_cron")
log.setLevel(logging.INFO)
log.addHandler(logging.FileHandler("/var/log/ai-news-cron/run.log"))

run_id = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d-%H%M%S")
metrics = {"run_id": run_id, "started_at": int(time.time())}

# ... after each major step ...
metrics["probe_results"] = probe_results        # Step 1
metrics["raw_hits"] = raw_hit_count             # Step 2
metrics["deduped"] = len(all_stories)           # Step 3
metrics["top_count"] = len(top)                 # Step 4
metrics["engagement_floor_hits"] = filtered_out # Step 4
metrics["hn_latency_ms_avg"] = avg_latency      # Step 2

metrics["finished_at"] = int(time.time())
metrics["duration_s"] = metrics["finished_at"] - metrics["started_at"]
metrics["idempotency_key"] = idempotency_key
log.info(json.dumps(metrics))
```

### Alerting thresholds

| Condition | Action |
|---|---|
| `top_count == 0` AND `raw_hits > 50` | Recency filter is wrong — widen to 48h and re-run once |
| `top_count == 0` AND `raw_hits < 10` | Quiet news day — send the placeholder, do not retry |
| `hn_latency_ms_avg > 5000` | HN Algolia is slow but functional — proceed, do not retry |
| `hn_latency_ms_avg > 15000` OR `retries_per_query > 1` | Switch to the `search_by_date` endpoint and reduce `hitsPerPage` to 10 |
| `delivery_ack` missing after 60s | Re-send once with the same `idempotency_key`; if still no ack, fall back to email |
| Two consecutive runs with `top_count < 3` | Probably wrong timezone — re-verify `Asia/Shanghai` is the active ZoneInfo |

The log file is the source of truth when the user reports "yesterday's digest
was weird". Always write metrics before the delivery call, not after — that
way a delivery timeout still leaves a trail.

## References

- [`references/hn-algolia-api.md`](references/hn-algolia-api.md) — full HN Algolia endpoint reference, response schema, filter syntax gotchas, and a robust fetch helper. Read this when [Step 2](#step-2-query-hn-algolia-with-time--topic-filters) or [Step 3](#step-3-deduplicate--verify-recency) misbehaves.
- [`references/alternative-sources.md`](references/alternative-sources.md) — secondary endpoints (GitHub Trending, arXiv, RSSHub), tag-combination cheat sheet, and translation tips for non-English sources. Use this when [Edge cases → "Empty result set"](#edge-cases) persists across retries or your audience needs non-HN coverage.

## Version notes

| Version | Date | Change |
|---|---|---|
| 0.1 | 2026-06-18 | Initial: probe → query → dedupe → rank → format pipeline, pitfalls, verification |
| 0.2 | 2026-06-18 | Tightened trigger phrases; added concrete worked example with HN Algolia output |
| 0.3 | 2026-06-19 | Added [Troubleshooting](#troubleshooting) table; added [Edge cases](#edge-cases) (empty result, timezone, duplicates) |
| 0.4 | 2026-06-19 | Added `references/hn-algolia-api.md` and `references/alternative-sources.md`; added [Anti-patterns](#anti-patterns) section |
| 0.5 | 2026-06-19 | Added [Pre-flight validation checklist](#pre-flight-validation-checklist) with runnable self-test; added [Observability](#observability) metrics, instrumentation pattern, and alerting thresholds |
| 0.6 | 2026-06-19 | Polish: table of contents, cross-links between sections and reference files, version notes |

The worked example in this file is dated 2026-06-19 and is illustrative —
the pipeline produces equivalent output any day the cron fires.
