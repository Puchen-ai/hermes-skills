---
name: shop-spider
description: |
  生产级中文电商/团购爬虫框架,基于 news-spider 模式扩展,共享 fetchers/utils/storage。
  支持 4 大平台:京东 / 淘宝·天猫 / 美团·大众点评 / 拼多多。
  能力:商品列表+详情解析、商家+团购抓取、价格监控+历史趋势+降价告警、JSON/CSV/NDJSON 导出、内存倒排索引搜索。
  存储:MySQL(项目默认且唯一生产选项,utf8mb4)。SQLite 仅作为离线 demo 脚本的兜底,代码里显式传 sqlite 路径才会触发。
  内置反爬对抗(Mobile UA 轮换、Referer 伪造、1.5-3.5s 限速)。
  触发场景:商品比价、价格监控、团购信息抓取、本地商家数据采集、降价提醒、竞品价格跟踪。
---

# Shop Spider (电商/团购爬虫) v2.0

## 项目位置
`/root/news_spider/`(与新闻爬虫合并管理,共享底层工具)

## 数据库策略（**MySQL 唯一**）

与 `news-spider` 一致：**默认且强制使用 MySQL 8**。SQLite 已被降级为"离线 demo 兜底"，仅 `PriceRepository("path.db")` 显式传 sqlite 路径才会触发。

**生产代码、cron 任务、定时监控** 一律走 `PriceRepository()`（不传参）→ MySQL 的 `shop_spider` 库。

## 适用场景
- 🛒 **商品比价/监控** — 京东/淘宝/拼多多价格跟踪、降价提醒
- 🍱 **团购采集** — 美团/大众点评本地生活团购
- 🏪 **商家数据** — 美团商家信息(评分/地址/电话/营业时间)
- 📈 **价格趋势** — 历史曲线 + 线性回归预测
- 🔍 **全文搜索** — 倒排索引(支持中文 2-gram + 英文词)
- 📦 **数据导出** — JSON / CSV / NDJSON / gzip

## 一句话总结能力

| 能力 | 实现 | 测试覆盖 |
|---|---|---|
| 4 平台商品列表+详情解析 | ✅ | ✅ 4 套 fixture |
| 美团商家+团购+城市路由 | ✅ | ✅ |
| 反爬(Mobile UA + Referer + 限速) | ✅ | ✅ 17 |
| MySQL 价格历史 (SQLAlchemy ORM) | ✅ | ✅ 7 |
| 降价告警(阈值可配) | ✅ | ✅ 4 |
| 线性回归趋势预测 | ✅ | ✅ 5 |
| JSON/CSV/NDJSON/gzip 导出 | ✅ | ✅ 7 |
| 倒排索引全文搜索 | ✅ | ✅ 4 |
| CLI 集成(crawl/track/history) | ✅ | E2E ✅ |
| **测试总数** | — | **276 passed** |

## 快速使用

### 安装

```bash
cd /root/news_spider
pip install -r requirements.txt
# 京东/淘宝/拼多多可能需要 playwright:
pip install playwright
playwright install chromium
```

### 1. 抓取商品列表(CLI)

```bash
cd /root/news_spider
python3.8 main.py shop crawl --platform jd --keyword "iPhone" --pages 2 --output jd.json
python3.8 main.py shop crawl --platform taobao --keyword "手机" --output tb.csv --format csv
python3.8 main.py shop crawl --platform pdd --keyword "手机" --output pdd.ndjson --format ndjson
python3.8 main.py shop crawl --platform meituan --keyword "火锅" --city beijing
```

### 2. 价格监控(CLI)

```bash
# 添加监控项
python3.8 main.py shop watchlist-add --platform jd --sku-id 100012345 --threshold 0.1
python3.8 main.py shop watchlist-add --platform taobao --sku-id 1234567890 --title "iPhone 15 Pro"

# 运行监控
python3.8 main.py shop track --watchlist watchlist.json

# 查看历史+趋势
python3.8 main.py shop history --platform jd --sku-id 100012345 --days 30
```

### 3. Python API

```python
import sys
sys.path.insert(0, "/root/news_spider/src")

from spider.shop_parsers import JdAdapter, TaobaoAdapter, MeituanAdapter, PddAdapter
from spider.shop_fetchers import StealthFetcher
from spider.shop_export import export_products, search_products, ShopSearchIndex
from spider.shop_trackers import (
    PriceTracker, PriceRepository, WatchItem, compute_trend
)

# --- 单平台抓取 ---
adapter = JdAdapter()
urls = adapter.search_urls("iPhone", page=1)        # 列表 URL
products = adapter.parse_search_list(html, "iPhone") # 解析列表
detail = adapter.parse_product_detail(detail_html, detail_url)  # 解析详情

# --- 反爬抓取 ---
with StealthFetcher() as sf:
    resp = sf.get("https://search.jd.com/Search?keyword=iPhone")
    products = adapter.parse_search_list(resp.text, "iPhone")

# --- 美团商家+团购 ---
meituan = MeituanAdapter()
shop = meituan.parse_shop(shop_html, shop_url)       # Shop 对象
deal = meituan.parse_deal(deal_html, deal_url)       # Deal 对象
print(f"{shop.name} 评分 {shop.rating} 人均 ¥{shop.avg_price}")
print(f"{deal.title} ¥{deal.sale_price} (原价 ¥{deal.original_price})")

# --- 价格监控 ---
def fetch_price(platform, sku_id):
    """用户自定义:从任何数据源取价,返回 PriceRecord"""
    from decimal import Decimal
    return PriceRecord(platform=platform, sku_id=sku_id, price=Decimal("99"))

# 默认走 MySQL (.env: SHOP_DATABASE_URL)
repo = PriceRepository()   # → MySQL 的 shop_spider 库
# 离线 demo 可显式传 sqlite 路径(不推荐用于生产)
# repo = PriceRepository("data/shop_history.db")
tracker = PriceTracker(repo, fetch_price)
items = [WatchItem(platform="jd", sku_id="100012345", threshold_pct=0.1)]
tracker.check_all(items)  # 自动记录+告警

# --- 历史 + 趋势 ---
history = repo.history("jd", "100012345", days=30)
trend = compute_trend(history)
print(f"趋势: {trend.direction}  预测下期 ¥{trend.forecast_next}")

# --- 导出 ---
export_products(products, "out.json", fmt="json", compress=True)
export_products(products, "out.csv", fmt="csv")

# --- 搜索 ---
hits = search_products(products, "iPhone", fields=["title", "shop_name"])
idx = ShopSearchIndex()
for p in products: idx.add(p)
results = idx.search("iPhone")
```

## 项目结构(shop 部分)

```
src/spider/
├── shop_models.py              5 个数据模型 (Product/PriceRecord/Shop/Deal/Review)
├── shop_site_adapter.py        ShopSiteAdapter Protocol
├── shop_export.py              导出 + 搜索 + 倒排索引
├── shop_parsers/
│   ├── jd_parser.py            京东 (列表+详情)
│   ├── taobao_parser.py        淘宝/天猫 (g_page_config JSON)
│   ├── meituan_parser.py       美团 (商家+团购+deal_list)
│   └── pdd_parser.py           拼多多 (rawData JSON)
├── shop_fetchers/
│   └── stealth_fetcher.py      反爬 (UA 轮换+Referer+限速)
└── shop_trackers/
    └── price_tracker.py        价格监控 (watchlist+SQLite+告警+趋势)

tests/
├── test_shop_models.py         28 tests
├── test_jd_parser.py           22 tests
├── test_taobao_parser.py       26 tests
├── test_meituan_parser.py      30 tests
├── test_pdd_parser.py          21 tests
├── test_stealth_fetcher.py     17 tests
├── test_price_tracker.py       21 tests
├── test_shop_export.py         18 tests
└── fixtures_*.py               离线 HTML fixtures

scripts/
└── demo_e2e.py                 端到端集成演示 (无需网络)
```

## 核心数据模型

| 模型 | 关键字段 | 用途 |
|---|---|---|
| **Product** | platform, sku_id, title, url, price (Decimal), original_price, sales, rating, brand, category, shop_name, image_url | 商品主数据 |
| **PriceRecord** | platform, sku_id, price, original_price, in_stock, ts | 单次价格观测 |
| **Shop** | platform, shop_id, name, rating, review_count, address, city, phone, avg_price, business_hours | 商家/店铺 |
| **Deal** | platform, deal_id, title, shop_id, sale_price, original_price, sold_count, expires_at | 团购/优惠券 |
| **Review** | platform, sku_id, review_id, content, rating, user_hash (脱敏) | 用户评价 |

所有模型都有:
- `__post_init__` 校验必填字段
- 价格自动转 `Decimal`(不丢精度)
- `to_dict()` 用于 JSON/CSV 序列化
- 平台特定的 `url_hash` 用于去重

## 反爬策略 (StealthFetcher)

| 平台 | UA 策略 | Referer |
|---|---|---|
| 京东 | 桌面 | https://www.jd.com/ |
| 淘宝/天猫 | **移动** (iPhone/Android) | https://www.taobao.com/ |
| 美团 | **移动** | (根) |
| 拼多多 | **移动** | https://mobile.yangkeduo.com/ |
| 其它 | 桌面 | (根) |

附加 headers: `Accept-Language: zh-CN,zh;q=0.9`、禁用缓存、合理 Accept 头

限速: 1.5-3.5s 随机间隔(可在 `StealthFetcher(min_interval=..., max_interval=...)` 调)

## 价格监控流程

```
[1] 用户编辑 watchlist.json:
    [{"platform":"jd","sku_id":"100012345","threshold_pct":0.1,"title":"iPhone 15 Pro"}]

[2] 定时任务运行 main.py shop track
    -> StealthFetcher 抓详情页
    -> parse_product_detail() 解析当前价
    -> PriceRecord 入库 (MySQL/SQLite 自动判定)
    -> 与上次价格对比
    -> drop >= threshold_pct? -> 触发告警回调

[3] 用户运行 main.py shop history
    -> 从存储后端取 N 天历史
    -> compute_trend() 线性回归
    -> 打印 min/max/avg/slope/forecast
```

## 端到端演示 (无需网络)

```bash
cd /root/news_spider && python3.8 scripts/demo_e2e.py
```

输出:
```
[1/5] 多平台抓取   jd:3, taobao:3, pdd:3 = 9 商品
[2/5] 全文搜索    iPhone: 4 命中
[3/5] 倒排索引    华为: 2 命中
[4/5] 美团商家+团购  海底捞 (4.8分, 人均¥128) / 团购¥198 (折34%, 售5621)
[5/5] 价格监控    告警: 降价-20% (¥100 -> ¥80), 趋势: down
[BONUS] 导出       JSON 5545B / CSV 2305B
✅ 全部链路 OK
```

## 测试

```bash
cd /root/news_spider
python3.8 -m pytest                              # 全部 276 测试
python3.8 -m pytest tests/test_jd_parser.py -v   # 京东 22
python3.8 -m pytest tests/test_price_tracker.py -v  # 价格监控 21
```

## 法律与伦理约束
- ✅ 严格遵守 `robots.txt` 和各平台 ToS
- ❌ 不绕过登录态、签名、付费墙
- ❌ 不大规模抓取造成对方服务器压力(限速 1.5-3.5s 强制)
- ❌ 个人信息做脱敏(Review.user_name 只保留首字 + ***)
- ❌ 数据仅供个人分析/学习,不商业分发

## 平台抓取难度评估

| 平台 | 难度 | 主要挑战 | 已实现 |
|---|---|---|---|
| 京东 | 🟡 中 | 部分价格 JS 渲染 | 列表 3 种策略(JSON + 标签 + 锚点 fallback) |
| 淘宝/天猫 | 🟠 中高 | g_page_config 深度嵌套 | `_walk` 递归走多路径 |
| 美团 | 🟡 中 | SVG 矢量文字防爬 + 城市路由 | 静态部分解析完整 |
| 拼多多 | 🟠 中高 | 几乎全 JS,价格在分 | rawData JSON 优先,fallback 锚点 |

## Pitfalls(踩坑提示)

1. **京东价格不直接出现在 HTML** — 在 `<script>` 的 `pageData` JSON 里,正则提取后 `_extract_json_prices()` 映射 skuId → price
2. **淘宝价格有分/元两种单位** — `_normalize_price()` 用启发式: int > 10000 视为分
3. **美团用了 SVG 矢量图防爬** — 部分价格/评分以 `<text>` 渲染,需要 OCR 兜底(本版本不支持)
4. **拼多多价格永远在分** — `_cents_to_yuan()` 无脑除 100
5. **不要在生产环境无限制抓美团** — 触发风控后 IP 进黑名单
6. **时间戳统一** — 美团用 10 位秒,京东用 13 位毫秒,本框架统一 ISO 字符串
7. **倒排索引中文 2-gram** — 不依赖 jieba,但单字查询会落空(避免高噪声)
8. **StealthFetcher 改 settings** — 因为 `HttpFetcher` 从 settings 读限速参数,构造时已重写

## 添加新平台(3 步)

1. 写 parser: `src/spider/shop_parsers/xxx_parser.py`,实现 `parse_search_list` + `parse_product_detail`
2. 写 Adapter: 同文件下加 `XxxAdapter` 类
3. 注册: `src/spider/shop_parsers/__init__.py` 导出 + `main.py:_shop_adapter()` 添加映射
4. (可选) 写 fixture + 单元测试,沿用 `tests/fixtures_xxx.py` 模式

## 已知限制

- ❌ **Playwright fallback** 未实现 — 高度 JS 渲染的页面(纯拼多多/美团手机版 SPA)需要 headless browser
- ❌ **登录态抓取** 未支持 — 评论详情、淘宝登录后价格
- ❌ **分布式** 未实现 — 单机 MySQL (已支持,但无 sharding)
- ❌ **OCR** 未实现 — 美团 SVG 文字 / 滑动验证码
- ❌ **PromQL/通知** 未实现 — 告警回调是用户传入的函数,可对接 wechat/email/钉钉

## 后续可能扩展

- [ ] 1688 / 亚马逊中国 / 唯品会
- [ ] Playwright 渲染器(`shop_fetchers/playwright_fetcher.py`)
- [ ] 滑动验证码识别(ddddocr / 第三方 API)
- [ ] 价格对比报告(同 SKU 跨平台)
- [ ] 微信公众号/钉钉机器人告警
- [ ] 增量更新(基于 crawled_at 增量抓)
