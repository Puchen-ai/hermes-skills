# Cache File Format Reference

The decision tree in `SKILL.md` depends on being able to (a) find the cache, (b) read its staleness metadata, and (c) decide whether to serve it. This document specifies the on-disk layout so multiple cron jobs and agents agree.

## Location

`~/.hermes/cache/<job-name>/<date>.json`

- `~/.hermes/cache/` — root, created on first run if missing
- `<job-name>` — kebab-case slug, must match the cron job name (e.g., `ai-news-daily-cron`)
- `<date>` — ISO date in UTC (`YYYY-MM-DD`); the day the fetch *targeted*, not the day it ran

Example: `~/.hermes/cache/ai-news-daily-cron/2026-06-19.json`

## Schema (v1)

```json
{
  "schema_version": 1,
  "job": "ai-news-daily-cron",
  "fetched_at": "2026-06-19T07:58:42Z",
  "fetched_at_tz_note": "host TZ was UTC; cron uses UTC",
  "sources_attempted": 10,
  "sources_succeeded": 10,
  "sources_failed": [],
  "items": [
    {
      "title": "Example headline",
      "url": "https://example.com/article",
      "source": "TechCrunch",
      "published_at": "2026-06-19T07:30:00Z",
      "summary": "One- or two-sentence summary."
    }
  ],
  "ttl_policy": {
    "fresh_hours": 24,
    "stale_days": 7
  }
}
```

### Required fields

| Field | Type | Notes |
|---|---|---|
| `schema_version` | int | Bump on breaking changes. Consumers must reject unknown versions. |
| `job` | string | Matches directory name; sanity check on read. |
| `fetched_at` | ISO 8601 UTC | Use this for staleness math. Never trust local time. |
| `sources_attempted` | int | Total sources the run tried. |
| `sources_succeeded` | int | Subset that returned real content. |
| `sources_failed` | array of strings | Source names or URLs that failed, for transparency. |
| `items` | array | The actual digest payload. May be empty if `sources_succeeded == 0`. |
| `ttl_policy` | object | `fresh_hours` (default 24) and `stale_days` (default 7). |

### Staleness decision

```
age_hours = (now_utc - fetched_at) / 3600
if age_hours < ttl_policy.fresh_hours:
    serve as fresh, no label
elif age_hours < ttl_policy.stale_days * 24:
    serve with staleness label "⚠️ Cached snapshot from YYYY-MM-DD"
else:
    discard; emit [SILENT]
```

## Lockfile

Path: `~/.hermes/cache/<job-name>/.lock`

Acquire with `flock -n` before any write to the cache dir. If the lock cannot be acquired, a previous run is still going — exit silently so the previous run's output is the one delivered.

```bash
exec 9>/home/<user>/.hermes/cache/ai-news-daily-cron/.lock
flock -n 9 || { echo "[SILENT] previous run in progress"; exit 0; }
```

The lockfile should not contain data; it is created by `flock` itself. To clean up a stale lock from a crashed run, check the mtime and delete if older than 2x the cron interval.

## Failure log

Path: `~/.hermes/logs/cron-failures.log`

One JSON line per run that ended in `[SILENT]` or partial failure:

```
{"ts":"2026-06-19T08:00:03Z","job":"ai-news-daily-cron","outcome":"SILENT","reason":"web-access-blocked","pattern_key":"tirith:unknown","cache_state":"miss"}
{"ts":"2026-06-19T08:00:03Z","job":"ai-news-daily-cron","outcome":"PARTIAL","reason":"paywall","sources_succeeded":7,"sources_attempted":10}
```

Plain-text one-liners are also acceptable for quick debugging:

```
2026-06-19T08:00:03 ai-news-daily-cron SILENT web-access-blocked cache-miss
```

Pick one format and stick to it across jobs — agents will grep this file across runs.

## Versioning policy

- `schema_version: 1` — current
- A consumer reading a file with a higher schema_version than it understands must skip the file and fall through to `[SILENT]` or to a fresh fetch if web access is available
- Never silently coerce across schema versions; the on-disk shape is the contract