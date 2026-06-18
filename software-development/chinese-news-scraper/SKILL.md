---
name: chinese-news-scraper
description: Build Python web scrapers for Chinese news sites (Sina, NetEase, Tencent). Trigger when user wants to scrape Chinese news, build a news aggregator, or set up a Chinese-language web crawler with anti-crawling etiquette and database storage.
---

# Chinese News Scraper — Reusable Approach

A battle-tested approach for building a robust Chinese news scraper in Python, learned from a 9-round iterative project targeting Sina News (新浪新闻).

## When to Use This Skill

- User wants to scrape Chinese news websites (Sina, NetEase, Tencent, etc.)
- Building a news aggregator or content monitoring system
- User needs persistent storage (SQLite/PostgreSQL) for scraped articles
- User wants a polite, retry-capable, deduplicated crawler

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

## Verification Checklist

Before declaring done:
- [ ] End-to-end crawl produces 0 errors on real network
- [ ] Repeat run shows 0 new (dedup working)
- [ ] DB query for one article shows clean title, decoded content, no ad text
- [ ] Export to JSON works
- [ ] All unit tests pass (parsers, models, storage, utils, errors)
- [ ] Integration tests pass with mocked HTTP
- [ ] Chinese encoding works (test with `测试` not just ASCII)

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
