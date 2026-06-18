# Alternative sources

When HN Algolia is unreachable, or your audience needs coverage of non-HN
topics (Chinese AI labs, policy, funding), layer these endpoints on top of the
base workflow. All are reachable from a typical sandboxed environment and
require no API key.

## Quick decision matrix

| Need | Endpoint | Notes |
|---|---|---|
| Chinese AI labs (DeepSeek, Qwen, Kimi) | `news.ycombinator.com` via Algolia, **and** Twitter `search.json` (often blocked) | Algolia's `query=Qwen` finds Western coverage of Qwen releases; native Chinese coverage is rarely on HN. |
| Funding / M&A | `https://hn.algolia.com/api/v1/search?query=acquired+OR+raised&tags=story` | Search for the verbs, not the companies — broader recall. |
| Policy / regulation | Add `EU+AI+Act`, `AI+regulation`, `AI+executive+order` queries | Combine with the standard 24h window. |
| Research papers | Algolia `query=paper&tags=story` + filter `points>=30` | Filters out blog reposts of random arXiv papers. |
| Show HN tools | `tags=show_hn` (use in a separate call, not mixed with `tags=story`) | Mixing tags is AND-ed server-side and will return nothing. |

## Tag combinations cheat sheet

```
tags=story                     # canonical stories only
tags=story,show_hn             # AND: nothing — show_hn is not a story type
tags=show_hn                   # Show HN posts (always also have _tags=story)
tags=ask_hn                    # Ask HN posts
tags=story,author_<username>   # Stories by a specific user
```

If you want "Show HN stories with X points", query twice and merge:
`tags=story` (broader) and `tags=show_hn` (narrower, filtered to 100+ points).

## Secondary endpoints worth knowing

### GitHub Trending (no key, sometimes reachable)

```
https://github.com/trending/python?since=daily
```

Useful for "what AI tooling shipped this week" but the HTML scraper needs
care. Skip in cron — use only on-demand.

### arXiv listings

```
https://arxiv.org/list/cs.AI/recent
```

Often blocked in sandboxes. If you can reach it, it complements HN by
catching papers 1-2 days before they hit the front page.

### RSS via RSSHub (community instances)

```
https://rsshub.app/hackernews/best
https://rsshub.app/36kr/hot-lists
```

Block list varies; probe first. RSSHub requires a public instance — not
suitable for production cron without self-hosting.

## Translation tip for non-English sources

When pulling from Chinese sources (36kr, 机器之心, 量子位), the
title is often already informative. Do **not** rely on the LLM to translate
the whole article — translate only:
- The title (1 line)
- The lede sentence (1-2 lines)
- Numbers and proper nouns verbatim

Everything else, link to the source. The audience can read the original;
your value is the ranking and curation, not full translation.
