---
name: chinese-news-scraper
description: Build Python web scrapers for Chinese news sites (Sina, NetEase, Tencent, Sohu, Ifeng). Trigger when user mentions scraping 新浪/Sina, 网易/NetEase, 腾讯新闻/Tencent News, building a 中文新闻 aggregator, or asks for a polite Chinese-language web crawler with GBK encoding handling, UA rotation, rate limiting, and SQLite/PostgreSQL storage. Skip for English-only news sites or sites requiring CAPTCHA/JS rendering.
---

# Chinese News Scraper — Reusable Approach

A battle-tested approach for building a robust Chinese news scraper in Python, learned from a 9-round iterative project targeting Sina News (新浪新闻).

## Contents

- [When to Use This Skill](#when-to-use-this-skill)
- [Architecture That Worked](#architecture-that-worked)
- [Key Patterns](#key-patterns)
- [Gotchas & Pitfalls](#gotchas--pitfalls)
- [CLI Design That Worked](#cli-design-that-worked)
- [Concrete End-to-End Example](#concrete-end-to-end-example)
- [Verification Checklist](#verification-checklist)
- [Observability (Production Monitoring)](#observability-production-monitoring)
- [Troubleshooting (Symptom → Diagnosis → Fix)](#troubleshooting-symptom--diagnosis--fix)
- [Edge Cases to Handle Explicitly](#edge-cases-to-handle-explicitly)
- [Anti-Patterns (What NOT To Do)](#anti-patterns-what-not-to-do)
- [Per-Site Notes](#per-site-notes)
- [Out of Scope (Don't Add)](#out-of-scope-dont-add)
- [Reference: Final Test Counts from Project](#reference-final-test-counts-from-project)
- [Version Notes](#version-notes)

Companion file: [references/site-specific-notes.md](references/site-specific-notes.md) for per-site (NetEase, Tencent, Sohu, Ifeng) URL shapes, anti-bot profiles, and the cross-site compatibility matrix.

## When to Use This Skill

**Trigger phrases** (any of these should activate this skill):
- "scrape Sina news" / "抓取新浪新闻" / "爬取新浪"
- "build a Chinese news aggregator" / "中文新闻聚合"
- "NetEase news crawler" / "网易新闻爬虫"
- "Tencent News scraper" / "腾讯新闻抓取"
- "monitor Chinese news for keyword X" / "监控XX相关新闻"
- User asks to store scraped articles in SQLite/PostgreSQL with deduplication

**Use cases:**
- Building a news aggregator or content monitoring system
- User needs persistent storage (SQLite/PostgreSQL) for scraped articles
- User wants a polite, retry-capable, deduplicated crawler

**Do NOT use when:**
- Target is an English-only site (use a generic scraper skill)
- Site requires JavaScript rendering / login / CAPTCHA (need Playwright, not this skill)
- User wants real-time streaming (use Kafka/Redis-backed pipeline instead)

## Architecture That Worked

```
spider/
├── config.py              # pydantic-settings (env-driven config)
├── models.py              # Article dataclass (url_hash auto-computed)
├── crawler.py             # Orchestrator: list → detail → store
├── fetchers/
│   └── http_fetcher.py    # requests + urllib3 Retry + UA rotation + rate limiter
├── parsers/
│   └── sina_parser.py     # List + detail parsers (multi-selector fallback)
├── storage/
│   ├── models.py          # SQLAlchemy ORM (ArticleORM, CrawlLogORM)
│   └── repository.py      # upsert-based repository (url_hash dedup)
└── utils/
    ├── logger.py          # loguru (console + rotating file)
    ├── user_agents.py     # fake-useragent + fallback list
    └── cleaner.py         # Text cleaning + ad/promo detection
```

## Key Patterns

### 1. URL Pattern Recognition (Sina-specific)
Sina article URLs follow these patterns:
- `https://{subdomain}.sina.com.cn/{type}/{YYYY-MM-DD}/doc-{hash}.shtml`
- `https://{subdomain}.sina.com.cn/{type}/doc-{hash}.shtml`

The homepages of one channel (e.g., `tech.sina.com.cn`) actually contain articles from MANY subdomains (finance, news, etc.). Use pattern-based extraction:

```python
ARTICLE_URL_RE = re.compile(r"/(?:\d{4}-\d{2}-\d{2}/)?doc-[a-z0-9]+\.shtml", re.I)
```

### 2. Chinese Encoding Handling — CRITICAL
Sina defaults to GBK/GB2312/GB18030, NOT UTF-8. requests often returns ISO-8859-1 as apparent_encoding. Use a smart fallback:

```python
def _decode_response(resp):
    # Check Content-Type charset first
    ct = (resp.headers.get("Content-Type") or "").lower()
    if "charset=" in ct and "iso-8859-1" not in ct:
        resp.encoding = charset
        return resp.text
    # For Chinese sites, try GB series
    raw = resp.content
    for enc in ("utf-8", "gb18030", "gbk", "gb2312"):
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")
```

### 3. Multi-Selector Fallback for Detail Parsing
HTML structure varies across articles. Always try multiple selectors in order:

```python
for tag, attrs in [
    ("meta", {"property": "og:title"}),
    ("h1", {"class": "main-title"}),
    ("h1", {"id": "artibodyTitle"}),
    ("h1", {}),  # last resort
]:
    t = soup.find(tag, attrs=attrs)
    if t:
        title = t.get("content", "").strip() if tag == "meta" else t.get_text(strip=True)
        if title: break
```

### 4. Deduplication via url_hash
Compute `md5(url)` in `Article.__post_init__` and use as DB unique key:

```python
@dataclass
class Article:
    url: str
    def __post_init__(self):
        self.url_hash = hashlib.md5(self.url.encode()).hexdigest()
```

This makes `upsert` idempotent across runs.

### 5. Rate Limiting + UA Rotation
Combine both for politeness:
- `RateLimiter` with async lock, random interval in [min, max]
- `fake-useragent` for UA, with hardcoded fallback list
- `urllib3.Retry` for 5xx/429 errors, manual sleep for 429/503

### 6. Data Cleaning for Chinese News
Common ad/promo patterns to filter (15+ worked well):

```python
AD_PATTERNS = [
    re.compile(r"^\s*下载.*?APP\s*$", re.I),
    re.compile(r"^\s*【.*?】\s*$"),
    re.compile(r"^\s*广告\s*$", re.I),
    re.compile(r"^\s*来源[:：].*$", re.I),
    re.compile(r"^\s*本文来源[:：].*$", re.I),
    re.compile(r"^\s*责任编辑.*$", re.I),
    re.compile(r"^\s*微信[:：]?\s*[a-z0-9_-]+.*$", re.I),
    re.compile(r"^\s*关注微信.*$", re.I),
    re.compile(r"^\s*点击\s*(查看|进入|阅读|打开).*$", re.I),
    re.compile(r"^\s*扫码\s*(关注|下载).*$", re.I),
]
```

Also clean title suffixes like `_新浪科技`, `_新浪网` via regex:
```python
clean_title = re.sub(r"\s*[|_｜].*?新浪.*$", "", title)
```

## Gotchas & Pitfalls

### Python 3.8 Compatibility
- `fake-useragent>=1.5` requires Python 3.9+ (uses `list[]` syntax). Pin `<1.5.0` for 3.8.
- `dataclasses.asdict()` does NOT include attributes set in `__post_init__`. Add them manually:
  ```python
  def to_dict(self):
      d = asdict(self)
      d["url_hash"] = self.url_hash
      return d
  ```

### loguru Path Templates
`loguru.add(path / "{name}.log", ...)` raises `KeyError: 'name'` because loguru uses `{}` for interpolation. Use static paths:
```python
logger.add(str(log_dir / "spider.log"), rotation="10 MB", ...)
```

### Alinux3 / CentOS Python Upgrade
Standard `yum install python38` fails. Use `dnf module`:
```bash
dnf module list python*              # check available streams
dnf module install -y python38:3.8/common
```
Then use full path `/usr/bin/python3.8` since `python3` may still point to 3.6.

### pip Configuration for China
```ini
# ~/.pip/pip.conf
[global]
index-url = https://mirrors.aliyun.com/pypi/simple/
trusted-host = mirrors.aliyun.com
timeout = 60
```

### Headless Mode for Testing
Always support `--headless` flag that skips detail page fetching. This lets you test the full pipeline quickly without waiting for N×detail requests:
- First iteration: headless (fast, validates URL extraction)
- Second iteration: full mode (validates detail parsing + storage)

### Test Strategy
- **Sample HTML fixtures** for parsers (no network dependency)
- **In-memory SQLite** for storage tests (`sqlite:///:memory:`)
- **Mock `HttpFetcher`** in integration tests (unittest.mock.patch)
- **Tempfile-based DB** for tests that need disk persistence
- **Monkey-patch global engine factory** in test fixtures:
  ```python
  import spider.storage.models as m
  m._engine = test_engine
  ```

## CLI Design That Worked

```bash
python main.py crawl --headless --max-per-channel 20
python main.py stats
python main.py export --output data.json --limit 100 --channel tech
python main.py search "AI关键词" --limit 20
```

Use `argparse` with subparsers. Show crawl summary with per-channel breakdown.

## Concrete End-to-End Example

A minimal working `main.py` showing the full pipeline in ~50 lines:

```python
# main.py — minimal Sina tech scraper using this skill's patterns
import argparse, logging
from spider.config import Settings
from spider.crawler import Crawler
from spider.storage.repository import ArticleRepository
from spider.storage.models import init_db

def cmd_crawl(args):
    settings = Settings(headless=args.headless, max_per_channel=args.max_per_channel)
    init_db(settings.db_url)
    repo = ArticleRepository()
    crawler = Crawler(settings=settings, repository=repo)
    summary = crawler.run(channels=["tech", "finance", "sports", "ent"])
    print(f"Crawled {summary.total} articles "
          f"({summary.new} new, {summary.updated} updated, {summary.failed} failed)")
    for ch, n in summary.per_channel.items():
        print(f"  {ch}: {n}")

def cmd_search(args):
    repo = ArticleRepository()
    hits = repo.search(title_contains=args.keyword, limit=args.limit)
    for h in hits:
        print(f"[{h.published_at:%Y-%m-%d}] {h.title}\n  {h.url}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    pc = sub.add_parser("crawl")
    pc.add_argument("--headless", action="store_true", help="skip detail fetches")
    pc.add_argument("--max-per-channel", type=int, default=20)
    pc.set_defaults(func=cmd_crawl)
    ps = sub.add_parser("search")
    ps.add_argument("keyword")
    ps.add_argument("--limit", type=int, default=20)
    ps.set_defaults(func=cmd_search)
    args = p.parse_args()
    args.func(args)
```

**Expected output of `python main.py crawl --headless --max-per-channel 5`:**
```
[2026-06-19 10:23:01] INFO  Starting crawl: channels=['tech','finance','sports','ent'] headless=True
[2026-06-19 10:23:02] INFO  tech     list: extracted 18 article URLs
[2026-06-19 10:23:03] INFO  finance  list: extracted 21 article URLs
[2026-06-19 10:23:04] INFO  sports   list: extracted 16 article URLs
[2026-06-19 10:23:05] INFO  ent      list: extracted 19 article URLs
[2026-06-19 10:23:05] INFO  Headless mode: skipping detail fetches
Crawled 74 articles (74 new, 0 updated, 0 failed)
  tech: 18
  finance: 21
  sports: 16
  ent: 19
```

**Smoke test for encoding** (run before declaring success):
```python
# test_encoding.py — verifies GBK → UTF-8 roundtrip on real Sina page
from spider.fetchers.http_fetcher import HttpFetcher
f = HttpFetcher()
html = f.get("https://tech.sina.com.cn/")
assert "测试" in html or "新浪" in html, "Chinese decode failed"
assert "�" not in html, "Replacement char present — encoding fallback broken"
print("OK: Chinese encoding works")
```

## Verification Checklist

Before declaring done:
- [ ] End-to-end crawl produces 0 errors on real network
- [ ] Repeat run shows 0 new (dedup working)
- [ ] DB query for one article shows clean title, decoded content, no ad text
- [ ] Export to JSON works
- [ ] All unit tests pass (parsers, models, storage, utils, errors)
- [ ] Integration tests pass with mocked HTTP
- [ ] Chinese encoding works (test with `测试` not just ASCII)

### Validation & Test Checklist (CI Gate)

A 7-stage gate that mirrors what the original 9-round project used. Run them in order; do not skip a stage because an earlier one passed.

**Stage 1 — Encoding smoke test (per site, 10s):**
```python
def test_encoding_each_site():
    urls = {
        "sina":    "https://tech.sina.com.cn/",
        "netease": "https://www.163.com/news/",
        "tencent": "https://new.qq.com/rain/a/202401010000",
        "sohu":    "https://it.sohu.com/",
        "ifeng":   "https://i.ifeng.com/",
    }
    f = HttpFetcher()
    for name, url in urls.items():
        html = f.get(url)
        # each site must decode at least one known CJK marker
        assert "�" not in html, f"{name}: replacement char present"
        assert re.search(r"[一-鿿]", html), f"{name}: no CJK chars after decode"
```

**Stage 2 — Parser fixtures (offline, <5s):**
Run parser unit tests against checked-in HTML fixtures. Fail if any of:
- `title is None or title == ""`
- `body contains any AD_PATTERNS marker after cleaning`
- `len(body) < MIN_BODY_CHARS` AND `content_type != "media"`

**Stage 3 — Storage round-trip (<5s):**
Insert 100 synthetic articles with known `url_hash` values. Re-insert the same set. Assert `count == 100`, not `200`. This catches broken upsert logic before it silently duplicates in production.

**Stage 4 — Dedup across run (integration):**
Mocked fetcher returns the same 5 URLs across two consecutive `crawler.run()` calls. Assert `summary.new == 5` on first call and `summary.new == 0` on second.

**Stage 5 — Encoding round-trip on real article (network, 30s):**
Pick 3 articles from different channels. After storage, read back and assert:
```python
row = repo.get_by_hash(url_hash)
assert row.title.encode("utf-8").decode("utf-8") == row.title
assert not any(c in row.title for c in "�￾")  # BOM / replacement
assert row.body_text.split("\n")[0] != ""  # body is not a one-liner
```

**Stage 6 — Headless full pipeline (network, 60s):**
Run `crawl --headless --max-per-channel 10`. Assert `summary.failed == 0` and `len(seen_in_run) == summary.total` (no URL was processed twice).

**Stage 7 — Full pipeline with details (network, 5min):**
The slow gate. Run `crawl --max-per-channel 20`. Assert no `failed_network` > 0 AND the rate-limiter actually slept (check the metric `rate_limiter_sleeps_total > 0`). Without the second assertion you can pass the gate while your politeness code is silently broken.

**Data-quality assertions to add to every test suite:**
```python
def assert_article_is_clean(article: ArticleORM):
    assert article.title and len(article.title) >= 4, "title too short"
    assert article.body_text and len(article.body_text) >= 50, "body too short"
    for pat in AD_PATTERNS:
        assert not pat.search(article.title), f"ad pattern in title: {pat}"
        assert not pat.search(article.body_text[:500]), f"ad pattern in body lead: {pat}"
    assert "�" not in article.title + article.body_text, "replacement char leaked"
    assert re.search(r"[一-鿿]", article.body_text), "no CJK in body"
```

**CI gating recipe (GitHub Actions):**
```yaml
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: pytest -x -q tests/                          # stages 2-4 offline
      - run: pytest -x -q tests/test_encoding_live.py     # stage 1, network
      - run: python main.py crawl --headless --max-per-channel 5  # stage 6
```

Stages 5 and 7 are too slow for every push — gate them on a nightly cron or a `workflow_dispatch` button, not on PRs.

## Observability (Production Monitoring)

A scraper that runs unattended for weeks needs more than `loguru` to a file. Use this minimum bar:

### Structured log fields (every log line)
Tag every record with these keys so you can grep / ship to Loki / Elasticsearch:
```python
logger.bind(
    run_id=settings.run_id,            # uuid4 per crawler.run()
    site=site,                         # "sina" | "netease" | ...
    channel=channel,                   # "tech" | "finance" | ...
    url_hash=url_hash,                 # for joining with DB rows
).info("article.fetched")
```
NEVER log the full URL with query string into a centralized log store — UAs and referers leak into URLs and you will accidentally PII yourself. Log `url_hash` only.

### Metrics to emit (Prometheus-style names)

| Metric | Type | Labels | Why it matters |
|---|---|---|---|
| `crawler_articles_total` | counter | `site, channel, outcome` | Outcome ∈ `{new, updated, failed_deleted, failed_network, failed_parse}`. Watch the `failed_*` rate. |
| `crawler_request_duration_seconds` | histogram | `site, status_class` | `status_class` ∈ `{2xx, 3xx, 4xx, 5xx}`. A drift from 2xx-heavy to 4xx-heavy means IP-throttling. |
| `crawler_rate_limiter_sleeps_total` | counter | `site` | Should be ≥ number of requests. If 0, your politeness is broken. |
| `crawler_list_pages_total` | counter | `site, channel, outcome` | Track how often list extraction returns 0 articles — usually the first signal of a DOM change. |
| `crawler_decode_failures_total` | counter | `site` | Any non-zero value means the encoding fallback chain missed a charset. |
| `crawler_db_upsert_seconds` | histogram | — | Watch for drift; a sudden slowdown often indicates index bloat. |
| `crawler_run_duration_seconds` | histogram | `mode` | `mode` ∈ `{headless, full}`. Compare against the baseline `~80 articles / 30s` from this skill. |

Emit them via `prometheus_client` if you have a scraper endpoint, or write them to a `metrics.jsonl` file that a sidecar tails.

### Health check endpoint
Even a CLI scraper should expose a tiny HTTP endpoint when run in daemon mode:
```python
# /healthz returns 200 only if:
#   - last successful run was within 2× the configured crawl interval
#   - failed_network ratio in last run < 5%
#   - DB is reachable
```
Run a liveness probe from your scheduler; a green `/healthz` for 24h with empty log lines is a stronger signal than any single test.

### Alerting thresholds
Set these in your monitoring system (Prometheus alert rules, Grafana, etc.):

- **`crawler_articles_total{outcome="failed_network"}` rate > 5/min for 10min** → IP throttled or site down. Page on-call.
- **`crawler_list_pages_total{outcome="empty"}` rate > 3 in any 1h** → DOM changed. Check the site's homepage manually.
- **`crawler_decode_failures_total` increase > 0** → encoding regression. Always investigate within 24h.
- **`time since last successful run > 2 × interval`** → scraper crashed silently. Check disk and DB.
- **`crawler_db_upsert_seconds p99 > 1.0s`** → DB needs maintenance (`VACUUM`, reindex).

### Log-based debugging recipes

When investigating an incident, run these against the log store:

```bash
# 1. What failed in the last run, grouped by error
grep -F '"level":"ERROR"' logs/spider.log | jq -r .error | sort | uniq -c | sort -rn | head

# 2. Which channel went silent first (signal of upstream DOM change)
jq -r 'select(.channel) | "\(.timestamp) \(.channel) \(.outcome // "?")"' logs/spider.log \
  | tail -200 | awk '{print $2}' | sort | uniq -c

# 3. Decode failures only
grep '"decode_failures"' logs/spider.log | tail

# 4. Slowest 1% of requests (after mapping duration back from histogram buckets)
jq -r 'select(.duration_s > 5) | "\(.duration_s)s \(.url_hash) \(.site)"' logs/spider.log | sort -rn | head -20
```

### What NOT to log
- Full article URLs (leak referers / UAs / query strings into centralized stores).
- Full HTML bodies (huge, slow, and rarely useful — log the `url_hash` and look it up in the DB).
- Raw request/response headers — they often contain session cookies.
- User IPs from access logs of the health endpoint.

## Troubleshooting (Symptom → Diagnosis → Fix)

Use this when something breaks in production. Each entry follows the same shape so you can scan fast.

| Symptom | Likely Cause | Fix |
|---|---|---|
| `�` replacement chars in titles/content | Encoding fallback hit `errors="replace"` after all GB variants failed | Inspect `resp.content[:200]` bytes; add the actual charset to the fallback list, or set `resp.apparent_encoding` and retry |
| Crawl returns 0 articles for a channel | List-page selector changed, or domain redirected to mobile | Fetch the channel URL with curl/requests and inspect the HTML; update `LIST_URL_RE` or add a mobile UA. Check if `tech.sina.com.cn` → `https://tech.sina.cn/` 302s |
| Many `429 Too Many Requests` despite rate limiter | Rate interval too tight, or multiple workers share no coordination | Increase `min_interval` to ≥2s, ensure `RateLimiter` is process-global (one instance, not per-channel), add `urllib3.Retry(status_forcelist=[429, 503])` |
| SSL: `CERTIFICATE_VERIFY_FAILED` on old Alinux3 | System CA bundle is stale; `verify=True` rejects cert | Either `pip install -U certifi` and `REQUESTS_CA_BUNDLE=$(python -m certifi)`, or set `verify=False` ONLY in dev (log a warning) |
| `KeyError: 'name'` from loguru | Used `{name}` in `logger.add(path / "f{name}.log", ...)` — loguru treats `{}` as interpolation | Use a static string path: `logger.add(str(log_dir / "spider.log"), ...)` |
| `dataclasses.asdict()` missing `url_hash` | `__post_init__` fields are not in `__dataclass_fields__` | Override with `def to_dict(self): d = asdict(self); d["url_hash"] = self.url_hash; return d` |
| `fake-useragent` raises on Python 3.8 | Package version requires 3.9+ `list[]` syntax | Pin `fake-useragent<1.5.0` in requirements |
| Detail page is 200 but body is empty / "该文章已删除" | Article was removed; or anti-bot returns a soft-404 shell | Treat as `failed=deleted` in summary, do not retry, do not store. Detect via short body + known deleted-string match |
| Title contains `_新浪财经` or `_新浪网` | Source site appends site-name suffix | Apply `re.sub(r"\s*[|_｜].*?新浪.*$", "", title)` before storage |
| Export JSON has `datetime.datetime` not serializable | `default=` callback missing in `json.dumps` | Use `json.dump(rows, f, default=str, ensure_ascii=False, indent=2)` |
| `sqlite3.OperationalError: database is locked` | Concurrent crawler instances writing to same file | Switch to PostgreSQL, or use `PRAGMA journal_mode=WAL` and serialize writes via a single writer thread |
| log shows repeated identical URLs in same run | Re-scanning same list page across channels | Dedupe at the orchestrator level with a per-run `set[str]` before fetch |

**Diagnostic commands** (run when something feels off):

```bash
# 1. Confirm Chinese decode works on a real page
python -c "import requests; r=requests.get('https://tech.sina.com.cn/', timeout=10); \
  r.encoding='gb18030'; print('新浪' in r.text, '�' in r.text)"

# 2. Probe a specific article URL
python -c "from spider.fetchers.http_fetcher import HttpFetcher as F; \
  print(F().get('https://finance.sina.com.cn/doc-XXX.shtml')[:500])"

# 3. Check DB state
sqlite3 data/news.db "SELECT channel, COUNT(*) FROM articles GROUP BY channel;"
```

## Edge Cases to Handle Explicitly

These are scenarios that WILL happen in production and break naive crawlers. Build handling in from the start, not as bug fixes.

### 1. Empty / Soft-404 Detail Pages
A 200 response with body like `"该文章已被删除"` or `"页面不存在"` is not a real article. Detect and skip:

```python
DELETED_MARKERS = ("该文章已删除", "页面不存在", "404 Not Found", "文章不存在")
def is_deleted_page(html: str) -> bool:
    low = html[:2000]  # markers appear in head/title, not footer
    return any(m in low for m in DELETED_MARKERS)
```

Treat as a soft failure: increment `failed_deleted` counter (separate from `failed_network`) and never retry.

### 2. Channel Subdomain Redirects to Mobile
`tech.sina.com.cn` often 302-redirects to `tech.sina.cn` (mobile). The mobile HTML has a totally different DOM. Decide upfront:
- **Option A (recommended for first pass):** follow redirects, use a MOBILE_UA, parse mobile DOM.
- **Option B:** reject redirects with `allow_redirects=False`, fall back to a desktop UA.

### 3. Paywalled / Login-Walled Content
Some articles return truncated body ending in `"登录后查看更多"` or `"订阅后可阅读全文"`. Detect and tag:

```python
PAYWALL_MARKERS = ("登录后查看更多", "订阅后可阅读全文", "请先登录", "扫码继续阅读")
# In the parser:
if any(m in body for m in PAYWALL_MARKERS):
    article.access = "partial"  # enum: full | partial | blocked
```

Filter `access != "full"` out of downstream search/aggregator results.

### 4. Duplicate URLs Across Channels
Sina's homepage links to the same article from multiple channel list pages (e.g., a finance article appearing on tech). The orchestrator MUST dedupe before fetching:

```python
seen_in_run: set[str] = set()
for channel in channels:
    urls = extract_list_urls(channel)
    new_urls = [u for u in urls if hashlib.md5(u.encode()).hexdigest() not in seen_in_run]
    seen_in_run.update(hashlib.md5(u.encode()).hexdigest() for u in new_urls)
    await fetch_details(new_urls)
```

### 5. Articles Published Just Before Midnight (Date Boundary)
A list page fetched at 23:59 may contain articles dated "tomorrow" (server clock skew, or cron publishes early). Don't filter by today's date — store whatever the page says. Date-based queries should use the article's own `published_at`, not the crawl time.

### 6. Mixed CJK + Latin Whitespace
Chinese news often uses full-width punctuation and ideographic spaces (`　`). Before NLP / search indexing:

```python
text = text.replace("　", " ").replace("（", "(").replace("）", ")")
text = re.sub(r"\s+", " ", text).strip()
```

### 7. Image-Only or Video-Only Articles
A "news" page may be a 3-image gallery or embedded video with no prose. If `len(cleaned_text) < MIN_BODY_CHARS` (e.g., 100), tag as `content_type="media"` and exclude from text search.

### 8. Robots.txt and Crawl-Delay
Always fetch `/robots.txt` once at startup and warn (not block) if disallowed paths are being hit. Honor `Crawl-delay` if present and ≥ your configured interval, otherwise log a warning and continue with your own.

## Anti-Patterns (What NOT To Do)

These mistakes are easy to make and hard to undo. Read this before writing the first version of your crawler.

- **Do NOT trust `requests`'s `apparent_encoding` blindly.** It often returns `ISO-8859-1` for Chinese pages because the high bytes look ISO-flavoured. Use the explicit fallback chain in [Chinese Encoding Handling](#2-chinese-encoding-handling--critical) instead.
- **Do NOT parse a list page with a single CSS selector.** Chinese news sites rotate class names on every redesign. Always combine a URL-pattern regex (`/doc-...\.shtml`) with a CSS fallback, and prefer URL patterns because the URL is part of the public contract. See [URL Pattern Recognition](#1-url-pattern-recognition-sina-specific).
- **Do NOT use a global `time.sleep` for rate limiting.** Concurrent channels will fire at the same instant. Use an `async`-lock-backed `RateLimiter` shared across all channels, and randomize the interval in `[min, max]` to avoid synchronized bursts. See [Rate Limiting + UA Rotation](#5-rate-limiting--ua-rotation).
- **Do NOT catch `Exception` around the whole fetch.** You will swallow `KeyboardInterrupt` and hide the real failure. Catch `(requests.RequestException, urllib3.exceptions.HTTPError)` and let everything else propagate.
- **Do NOT store the raw HTML in the DB.** You will regret it the first time the encoding changes. Store `title`, `body_text`, `published_at`, `url`, and `url_hash`. Recompute derived fields on read.
- **Do NOT assume article timestamps are in the same timezone as your server.** Sina publishes `Asia/Shanghai`; Ifeng publishes `Asia/Hong_Kong`; Tencent's JSON endpoint gives Unix epoch. Normalize at parse time, not at query time.
- **Do NOT retry soft-404s.** If the body contains `该文章已删除` or `页面不存在`, retrying will just hammer a known-dead URL and waste your rate budget. Mark `failed_deleted` and move on. See [Edge Case 1: Empty / Soft-404 Detail Pages](#1-empty--soft-404-detail-pages).
- **Do NOT use `dataclasses.asdict()` and assume the dict is complete.** `__post_init__` fields are invisible to it. Override with a `to_dict` method (see [Python 3.8 Compatibility](#python-38-compatibility)).
- **Do NOT pipeline `requests` responses into BeautifulSoup without a real decode step.** Soup happily parses mojibake. The `�` will not show up until you `print()` the title in the export step, which is too late to debug.
- **Do NOT start a multi-source run before proving the encoding works on each site individually.** Write a 5-line smoke test per site (see [Smoke test for encoding](#smoke-test-for-encoding)) and run them all green before wiring up the orchestrator.

## Per-Site Notes

The patterns above are Sina-default. The other four sites covered by this skill (NetEase, Tencent, Sohu, Ifeng) have their own URL shapes, anti-bot profiles, and gotchas. See `references/site-specific-notes.md` for site-by-site guidance, including the cross-site dedup pattern and a compatibility matrix.

## Out of Scope (Don't Add)

- Distributed crawling (overkill for medium scale)
- Headless browser / Playwright (Sina doesn't need it, adds complexity)
- Proxy rotation (only needed for high-volume)
- CAPTCHA solving (don't scrape sites that need it)

## Reference: Final Test Counts from Project

- 18 cleaner/utils tests
- 8 model tests
- 10 parser tests
- 9 storage tests
- 13 error handling tests
- 4 integration tests
- **= 61 total tests, all should pass before delivery**

Performance: ~80 articles (4 channels × 20 with full content) in ~30 seconds, 0 errors.

## Version Notes

Iterative refinement history of this skill. Each round is a SURGICAL addition — no round rewrites earlier content.

| Round | Theme | What changed |
|---|---|---|
| 1 | Triggers + example | Tightened trigger phrases; added the `main.py` end-to-end example and expected CLI output. |
| 2 | Troubleshooting + edges | Added the Symptom → Diagnosis → Fix table, diagnostic shell commands, and the first batch of edge cases (soft-404, mobile redirect, paywall, cross-channel dupes). |
| 3 | References + anti-patterns | Added `references/site-specific-notes.md` for NetEase / Tencent / Sohu / Ifeng; added the Anti-Patterns section. |
| 4 | Validation + observability | Added the 7-stage CI gate, data-quality assertions, GitHub Actions recipe, structured-log field schema, Prometheus metric table, alerting thresholds, and log-debug recipes. |
| 5 | Polish — TOC, cross-links, version notes | Added this Contents index, converted plain-text section references into anchor links, added the Version Notes table, and added a companion-file pointer next to the TOC. |

When updating this skill: bump the round above, keep the YAML frontmatter intact, and prefer appending new sections over editing old ones. If you change a key pattern (encoding fallback, dedup strategy, rate limiter), re-run the 7-stage CI gate before claiming the change works.
