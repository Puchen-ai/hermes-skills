---
name: weibo-monitoring
description: Monitor Weibo user posts — why browser/curl approaches fail and what to use instead
triggers: ["weibo monitor", "微博监控", "weibo.com scraping"]
---

# Weibo Monitoring — What Actually Works

## ⚠️ BROKEN APPROACHES (do not use)

1. **Browser (`browser_navigate`)** — Weibo detects and crashes headless Chrome. Error: `page.goto: Page crashed`. Tried URLs:
   - `https://weibo.com/u/1281164657` ❌
   - `https://weibo.com/1281164657` ❌
   - `https://m.weibo.com/u/1281164657` ❌
   - `http://weibo.com/u/1281164657` ❌
   - `https://passport.weibo.com/visitor/...` ❌

2. **`python3 -c ...`** — Security scan (`tirith`) blocks `-c`/`-e` inline script execution.
   ```
   ⚠️ Security scan: security issue detected. Asking the user for approval.
   pattern_key: "tirith:unknown"
   ```

3. **`curl` shell commands** — Same security scan blocks them.

## ✅ WORKING ALTERNATIVES

- Use the `xitter` skill (X/Twitter CLI) if the user just wants microblog monitoring — it has a working tool
- For Weibo specifically: use the Weibo API (`open.weibo.com`) with authenticated OAuth tokens — browser scraping is not viable
- Consider third-party Weibo aggregator services if you must track public accounts without login