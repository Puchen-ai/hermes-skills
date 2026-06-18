---
name: shop-spider-quickstart
description: 5 分钟上手 shop-spider 的最小可运行示例
---

# Shop Spider 快速开始

## 1. 安装(已有则跳过)

```bash
cd /root/news_spider
pip install -r requirements.txt
```

## 2. 离线跑通(无需网络)

```bash
python3.8 scripts/demo_e2e.py
```

## 3. 第一次真实抓取

```bash
# 抓京东"iPhone"前 2 页,存 JSON
python3.8 main.py shop crawl --platform jd --keyword "iPhone" --pages 2 --output my_first.json

# 看结果
head -30 my_first.json
```

## 4. 第一次价格监控

```bash
# 加一个监控项
python3.8 main.py shop watchlist-add --platform jd --sku-id 100012345 --threshold 0.05

# 检查一次
python3.8 main.py shop track

# 看历史
python3.8 main.py shop history --platform jd --sku-id 100012345 --days 7
```

## 5. 定时任务(每小时跑一次)

```bash
crontab -e
# 加一行:
0 * * * * cd /root/news_spider && /usr/bin/python3.8 main.py shop track --watchlist watchlist.json >> logs/track.log 2>&1
```

## 6. Python 内嵌使用

```python
import sys
sys.path.insert(0, "/root/news_spider/src")
from spider.shop_parsers import JdAdapter
from spider.shop_fetchers import StealthFetcher

with StealthFetcher() as sf:
    resp = sf.get("https://search.jd.com/Search?keyword=iPhone")
    products = JdAdapter().parse_search_list(resp.text, "iPhone")
    for p in products[:5]:
        print(f"{p.title}  ¥{p.price}")
```

## 常见问题

**Q: 报 `bs4` ModuleNotFoundError?**
A: `pip install beautifulsoup4 lxml`

**Q: 京东只抓到了 0 个商品?**
A: JD 有反爬,可能被风控。降速(改大 `min_interval`)、或换 IP。

**Q: 淘宝/拼多多只抓到了空 list?**
A: 列表页 JS 渲染。详见 SKILL.md 已知限制 — 需要 Playwright 兜底。

**Q: 倒排索引搜不到 '米'?**
A: 中文用 2-gram,搜"小米"而非"米"。详见 SKILL.md Pitfalls #7。
