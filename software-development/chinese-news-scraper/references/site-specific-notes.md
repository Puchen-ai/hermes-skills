# Site-Specific Notes for Chinese News Scrapers

The main `SKILL.md` is Sina-centric because that is the site where the patterns were hardened over 9 rounds. This file captures what is known about the other four target sites so the same architecture can be extended without re-discovering the gotchas.

> If you only need Sina, you can skip this file. If you are building a multi-source aggregator, read the section for each source you plan to support.

---

## 1. NetEase News (网易新闻) — `news.163.com` / `3g.163.com`

### URL shapes
- Desktop: `https://www.163.com/news/article/{ID}.html`
- Mobile: `https://3g.163.com/news/article/{ID}.html` (often more reliable; the desktop page loads content via JS in some cases)
- List: `https://www.163.com/news/`, `https://news.163.com/domestic/`, `https://news.163.com/world/`

### Encoding
- Default UTF-8. Rarely a problem. Still keep the GBK fallback in `_decode_response` for safety on sub-pages.

### Anti-bot profile
- Moderate. Mobile UA usually works for both desktop and mobile URLs.
- Aggressive scraping from a single IP can trigger a JS challenge page (returns 200 with `var i=1;...` script). Symptom: page is short (< 5KB) and contains the string `var i=1;` near the top. Treat as soft-404.
- `Retry-After` header is honored when present.

### List-page gotchas
- The DOM is heavily built with `<div class="news_title">` wrappers. Prefer XPath `//a[contains(@href, "/news/article/")]` over CSS class selectors because NetEase rotates class names more often than URL patterns.
- Article URLs always contain a numeric ID (`/article/JR1234567890.html`). Validate with `re.compile(r"/article/[A-Z0-9]+\.html")`.

### Detail-page gotchas
- Body is inside `div.post_body` or `article` tag. Fallback: `<div id="content">`.
- End-of-article "相关推荐" block must be trimmed — it is not part of the article.
- Source attribution appears as `责任编辑：` followed by an editor name; the existing `AD_PATTERNS` already strips it.

### Recommended approach
1. Try desktop URL first.
2. If response < 5KB or contains `var i=1;`, retry with `allow_redirects=True` to the `3g.` subdomain and a mobile UA.
3. Use the same multi-selector fallback pattern from `SKILL.md` for the title.

---

## 2. Tencent News (腾讯新闻) — `news.qq.com` / `new.qq.com`

### URL shapes
- Modern: `https://new.qq.com/rain/a/{YYYYMMDD}{ID}` (most common as of 2024+)
- Legacy: `https://news.qq.com/a/{YYYYMMDD}/{ID}.htm`
- List: `https://news.qq.com/` (very JS-heavy, often unusable from `requests`)

### Encoding
- UTF-8.

### Anti-bot profile
- **High.** `news.qq.com` returns a JS-shell page to non-browser clients. The article list on the homepage is rendered client-side, so plain `requests` will not see article links.
- Workaround: use the `new.qq.com/rain/a/...` direct article URL pattern — once you have one article ID, subsequent articles from the same channel can be discovered via the Tencent News RSS endpoints or the WeChat public-account mirror.

### List-page gotchas
- Direct list-page scraping is **not recommended** for Tencent. Use one of:
  - The official RSS feeds (e.g. `https://r.inews.qq.com/web_feed/getNews` and the per-column endpoints — undocumented, fragile).
  - The `view.inews.qq.com` mobile JSON API (requires a referer and a `cookie`; rate-limited aggressively).
  - A search query via `https://www.sogou.com/web?query=site:new.qq.com+...` to bootstrap a seed list.

### Detail-page gotchas
- When you DO get a `new.qq.com/rain/a/...` page, it is server-rendered and parses cleanly.
- Title is in `h1.rich_media_title` (yes, the class is named after WeChat — Tencent reuses the template).
- Body is in `div.rich_media_content` with paragraphs tagged `p`. Strip all `<img>` from the body before text cleaning (Tencent inserts 1x1 tracking pixels inline).
- `media_type` and `category` are exposed in `meta` tags — record them in the `Article` model so you can filter news vs. video vs. gallery.

### Recommended approach
1. Treat Tencent as a "seed-driven" source: do not rely on list-page extraction.
2. Maintain a list of channels (财经/科技/体育/娱乐) and use the inews JSON endpoint once per channel per run, with a 5–10s interval.
3. If the JSON endpoint is blocked, fall back to a hand-curated list of column RSS feeds.

---

## 3. Sohu News (搜狐新闻) — `news.sohu.com` / `www.sohu.com`

### URL shapes
- `https://www.sohu.com/a/{ID}_{SUFFIX}` (this is the canonical article pattern)
- `https://news.sohu.com/{YYYYMMDD}/n{ID}.shtml` (legacy)
- List: `https://www.sohu.com/` (heavily JS-rendered; only the "first screen" articles are in the static HTML)

### Encoding
- Mixed. Most pages declare `charset=utf-8`, but some legacy subdomains still emit GBK. Keep the fallback chain in `SKILL.md`.

### Anti-bot profile
- Low-to-moderate. Standard `requests` with a rotating UA works for article pages.
- The homepage, however, requires JS to render most article cards. Use a channel-specific list URL instead of the homepage:
  - `https://news.sohu.com/` for news
  - `https://business.sohu.com/` for business
  - `https://it.sohu.com/` for tech
  - `https://sports.sohu.com/` for sports

### List-page gotchas
- Channel root pages (e.g. `it.sohu.com`) ARE server-rendered and contain article links in the static HTML — that is the way in.
- Article URLs share the same `/a/{ID}_...` pattern across all channels, which makes deduplication by URL hash reliable.
- Be careful: the same article can appear under `www.sohu.com/a/{ID}` and `it.sohu.com/a/{ID}`. The orchestrator-level `seen_in_run` set (per `SKILL.md` Edge Case 4) handles this naturally.

### Detail-page gotchas
- Title: `<h1>` (no stable class). Fall back to `og:title` meta first.
- Body: `<article>` or `<div class="article">` or `<div id="articleContent">`. Always try the most general fallback last.
- Sohu appends "扫描关注搜狐网" QR-code blocks at the end. Extend `AD_PATTERNS` with:
  ```python
  re.compile(r"^\s*扫描.*?关注.*?搜狐.*$", re.I),
  re.compile(r"^\s*扫码.*?搜狐.*$", re.I),
  ```

### Recommended approach
1. Use channel-root URLs for list extraction, not the homepage.
2. Dedupe heavily — content syndication means 60–80% of articles on a given day appear under multiple channel roots.
3. The same `_decode_response` and multi-selector patterns from Sina work without modification.

---

## 4. Ifeng News (凤凰网) — `news.ifeng.com` / `i.ifeng.com`

### URL shapes
- Desktop: `https://news.ifeng.com/c/{ID}` (modern)
- Legacy: `https://news.ifeng.com/a/{YYYYMMDD}/{ID}_0.shtml`
- Mobile: `https://i.ifeng.com/c/{ID}` (recommended for scraping — much cleaner HTML)
- List: `https://news.ifeng.com/`

### Encoding
- UTF-8 across the board.

### Anti-bot profile
- Moderate. Desktop pages sometimes return a 200 with a "请开启 JavaScript" shell. Mobile (`i.ifeng.com`) is more scraping-friendly.
- Honor `Crawl-delay: 2` from `/robots.txt` strictly; Ifeng actively throttles violators.

### List-page gotchas
- Channel pages like `https://news.ifeng.com/` do not expose article links in the static HTML beyond the first 5–10. Use `i.ifeng.com` for the list.
- The mobile list page uses lazy loading: only the first viewport is server-rendered. If you need more, look for a `<a class="load-more">` URL in the source and paginate manually.

### Detail-page gotchas
- Title is in `<h1>` (mobile) or `div.yh_news_title` (desktop). Use the mobile page.
- Body is in `div.text` or `article.article-content`. The text contains a lot of `<br>` for paragraph breaks — collapse them with `re.sub(r"(<br\s*/?>\s*){2,}", "\n\n", html)` before `get_text()`.
- End-of-article "猜你喜欢" recommendation block must be stripped. Detect by checking for the string `var recommendData` in the HTML and removing everything from the parent of that script tag onward.

### Recommended approach
1. Always use the mobile URL pattern (`i.ifeng.com/c/{ID}`) for both list and detail.
2. Strip the recommendation block before parsing the body.
3. Respect `robots.txt` — Ifeng will IP-block you within 100 requests if you don't.

---

## 5. Cross-Site Patterns

Things that apply to ALL five sites and that the orchestrator should handle once (not per site):

### Encoding fallback
The chain in `SKILL.md` (`utf-8 → gb18030 → gbk → gb2312 → replace`) covers every site above. Do not duplicate it per source.

### Ad/promo filtering
The `AD_PATTERNS` list in `SKILL.md` was written for Sina but works for 70% of patterns on all five sites. Add site-specific patterns as needed, but keep the base list shared.

### Deduplication
A `tech.sina.com.cn` article is sometimes reposted verbatim on `news.163.com`. The `url_hash` dedup from `SKILL.md` only catches duplicates within a site. For cross-site dedup, compute a `content_hash = md5(cleaned_body)[:16]` on insert and `SELECT` against it. This is cheap and prevents the same article from appearing N times in the aggregator.

### Time zones
- Sina: publishes with `Asia/Shanghai` (UTC+8) timestamps in the HTML.
- NetEase: same, but some old articles use `GMT`.
- Tencent: stores `publish_time` as a Unix epoch in the JSON endpoint.
- Sohu: HTML `meta article:published_time` is UTC+8 ISO.
- Ifeng: HTML uses `Asia/Hong_Kong` (UTC+8, but DST-aware — no DST since 1979 but the code is DST-aware).

Standardize to UTC+8 wall-clock time in your `Article.published_at` field. The display layer can re-render in any timezone.

### Rate limiting
The `RateLimiter` from `SKILL.md` should be a SINGLETON shared across all sources in a multi-source run. Do not give each site its own limiter — that defeats the politeness goal. The pattern is:

```python
# In the orchestrator constructor:
self.rate_limiter = RateLimiter(min_interval=2.0, max_interval=4.0)
self.sites = {
    "sina": SinaFetcher(self.rate_limiter, ...),
    "netease": NetEaseFetcher(self.rate_limiter, ...),
    ...
}
```

If you use multiple processes, switch to a token-bucket backed by Redis or a per-host `asyncio.Semaphore` to coordinate.

### Robots.txt
Each site has its own. The crawler should:
1. Fetch `/robots.txt` once per site at startup.
2. Cache the parsed `RobotFileParser` for the run.
3. Log a warning (NOT raise) if a planned URL is disallowed.
4. Honor `Crawl-delay` if present and ≥ your configured interval.

---

## 6. Site Compatibility Matrix

| Site    | Encoding | List-page scrapable | Detail-page scrapable | Mobile URL available | Anti-bot level |
|---------|----------|---------------------|------------------------|----------------------|----------------|
| Sina    | GBK/UTF-8| Yes (channel roots) | Yes                    | Yes (m.sina.cn)      | Low-Moderate   |
| NetEase | UTF-8    | Yes                 | Yes (prefer 3g.)       | Yes (3g.163.com)     | Moderate       |
| Tencent | UTF-8    | **No** (JS-only)    | Yes (direct URL)       | Yes (new.qq.com)     | High           |
| Sohu    | Mixed    | Yes (channel roots) | Yes                    | Partial              | Low-Moderate   |
| Ifeng   | UTF-8    | Partial (mobile only)| Yes (mobile only)      | Yes (i.ifeng.com)    | Moderate       |

Use this matrix when planning a new multi-source run. The "List-page scrapable: No" row for Tencent is the single biggest reason a unified architecture needs a "seed-driven" extension point.

---

## 7. When to Update This File

Add a new section here when:
- You have a working scraper for a site NOT listed above.
- The URL pattern or anti-bot profile of a listed site has shifted (Tencent and Ifeng both change selectors every 6–12 months).
- You discover a new cross-site pattern (e.g. a cleaning rule that works for 4/5 sites).

Do NOT duplicate content from `SKILL.md` here — link back to the relevant section. This file should be the "delta" from the Sina-default skill.
