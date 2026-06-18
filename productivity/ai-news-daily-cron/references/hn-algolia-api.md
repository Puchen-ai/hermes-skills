# HN Algolia API — Reference

Deep-dive on the endpoints and response shape the daily-cron skill depends on.
Use this when you need to debug a malformed query, parse a new field, or
extend the skill to a second source via the same client.

## Endpoint overview

| Endpoint | Purpose | Auth | Rate limit |
|---|---|---|---|
| `https://hn.algolia.com/api/v1/search` | Full-text + filter search | None | Soft ~10 req/s per IP |
| `https://hn.algolia.com/api/v1/search_by_date` | Same filters, sorted by `created_at` desc | None | Same as above |
| `https://hn.algolia.com/api/v1/items/:id` | One story + its comment tree | None | Same as above |
| `https://hn.algolia.com/api/v1/users/:username` | User profile + submission history | None | Same as above |

The daily-cron skill only uses `/api/v1/search`. Switch to `/api/v1/search_by_date`
when you want chronological sort server-side and can tolerate older stories
leaking into the top hits.

## Query parameters (search)

```
?query=<terms>
&tags=<csv>            # story | comment | poll | job | show_hn | ask_hn | author_<name>
&numericFilters=<expr> # created_at_i>1234567890,points>=5
&page=0
&hitsPerPage=20
&attributesToRetrieve=<csv>
&attributesToHighlight=<csv>
```

Multiple `numericFilters` are comma-separated in **one** parameter, not
repeated parameter names. Example:

```
numericFilters=created_at_i>1749000000,points>=5
```

## Numeric filter syntax gotchas

- Use unix **seconds** (`int(time.time())`), not milliseconds. HN Algolia
  silently ignores filters that look too large (e.g. `>1749000000000` matches
  everything).
- Operators: `>`, `<`, `>=`, `<=`, `=`. No `!=`.
- Field names: `created_at_i` (note the `_i` suffix — the integer version of
  `created_at`). The string `created_at` is **not** filterable.
- Combine with `,` in a single value: `numericFilters=created_at_i>X,points>=Y`.
  Sending two `numericFilters=` parameters is undefined; one server returns
  the last value, another returns 400.

## Response shape (truncated)

```json
{
  "hits": [
    {
      "objectID": "40382119",
      "title": "Anthropic releases Claude 4.5",
      "url": "https://anthropic.com/news/...",
      "author": "alice",
      "points": 812,
      "num_comments": 304,
      "created_at_i": 1749000123,
      "created_at": "2026-06-04T07:22:03Z",
      "_tags": ["story", "author_alice", "story_40382119"]
    }
  ],
  "nbHits": 1247,
  "page": 0,
  "hitsPerPage": 20,
  "nbPages": 63,
  "processingTimeMS": 4,
  "query": "Anthropic",
  "params": "query=Anthropic&tags=story"
}
```

### Field reference

| Field | Type | Notes |
|---|---|---|
| `objectID` | string | Stable per-story id. Use as dedup key. |
| `title` | string | May be null for polls / jobs. |
| `url` | string \| null | null = self-post. Fall back to `https://news.ycombinator.com/item?id={objectID}`. |
| `points` | int \| null | Older stories occasionally return `null` — coerce to `0` before sorting. |
| `num_comments` | int | Always present for stories; 0 for fresh ones. |
| `created_at_i` | int | Unix seconds. **The only** reliable recency field. |
| `created_at` | string | ISO-8601 in UTC. For display only. |
| `_tags` | array | Includes `story`, `poll`, `comment`, `show_hn`, `ask_hn`, plus per-entity tags. |

## Rate-limit and error responses

- `200` with `{"message": "Please wait..."}` envelope (no `hits` key) — back off
  for 1-2 seconds. The skill's `data.get('hits', [])` pattern handles this
  gracefully.
- `429` — exponential backoff starting at 1s, cap retries at 3 per query.
- `5xx` — body is HTML, not JSON. Wrap `json.loads` in `try/except JSONDecodeError`
  and log the first 200 chars for debugging.
- Empty `hits` array — usually means the recency filter is wrong (ms vs s) or
  the topic had no stories in the window. Not an error.

## Sample robust fetch (reference implementation)

```python
import json
import time
import urllib.request
import urllib.error

def fetch_hn(url: str, max_retries: int = 2) -> list[dict]:
    """Fetch HN Algolia search results with retry + rate-limit handling."""
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            body = urllib.request.urlopen(req, timeout=20).read()
            data = json.loads(body)
            if 'message' in data and 'hits' not in data:
                # Rate-limit envelope — back off and retry
                time.sleep(1 + attempt)
                continue
            return data.get('hits', [])
        except (urllib.error.URLError, json.JSONDecodeError) as e:
            last_err = e
            time.sleep(2 ** attempt)
    raise RuntimeError(f"hn fetch failed after {max_retries + 1} attempts: {last_err}")
```

## When to switch sources

HN Algolia is HN-centric — it covers OpenAI, Anthropic, big-name papers, and
Show HN launches well. It **misses**:
- Chinese AI labs (DeepSeek, Qwen, Kimi, Doubao) unless they hit HN frontpage
- Industry M&A / funding rounds reported only on TechCrunch / The Information
- Government AI policy from non-US regulators

If your audience needs coverage of those, see `alternative-sources.md` for
secondary endpoints that work alongside HN Algolia.
