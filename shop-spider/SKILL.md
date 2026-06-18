---
name: shop-spider
description: |
  生产级中文电商/团购爬虫框架,基于 news-spider 模式扩展,共享 fetchers/utils/storage。
  支持 4 大平台:京东 / 淘宝·天猫 / 美团·大众点评 / 拼多多。

  TRIGGER when the user asks to: 抓商品/抓价格/比价/价格监控/降价提醒/降价告警/价格历史/价格趋势/
  抓团购/抓商家/美团商家/大众点评/本地生活/抓京东/抓淘宝/抓天猫/抓拼多多/竞品价格跟踪/
  shop crawl/price tracker/watchlist/coupon scrape/电商爬虫/团购爬虫.
  DO NOT TRIGGER for: 纯新闻抓取(用 news-spider)、登录后才能看的订单/评论详情、验证码识别、
  商业再分发(违反各平台 ToS)。

  能力:商品列表+详情解析、商家+团购抓取、价格监控+历史趋势+降价告警、JSON/CSV/NDJSON 导出、内存倒排索引搜索。
  存储:MySQL(项目默认且唯一生产选项,utf8mb4)。SQLite 仅作为离线 demo 脚本的兜底,代码里显式传 sqlite 路径才会触发。
  内置反爬对抗(Mobile UA 轮换、Referer 伪造、1.5-3.5s 限速)。
---

# Shop Spider (电商/团购爬虫) v2.0

> **版本**:v2.0(2026-06 第五轮迭代)
> **变更历史**:
> - v1.0 — 4 平台基础抓取(京东/淘宝/美团/拼多多)
> - v1.5 — 加入价格监控 + 历史趋势 + 降价告警
> - v1.8 — 倒排索引 + 多格式导出 + StealthFetcher
> - v2.0 — Troubleshooting + Edge cases + 验证清单 + 可观测性 + Anti-patterns + references/ 子文件(quickstart / adapter-extension)

## 目录

- [项目位置](#项目位置)
- [数据库策略](#数据库策略mysql-唯一)
- [适用场景](#适用场景)
- [一句话总结能力](#一句话总结能力)
- [快速使用](#快速使用)
  - [安装](#安装)
  - [抓取商品列表(CLI)](#1-抓取商品列表cli)
  - [价格监控(CLI)](#2-价格监控cli)
  - [Python API](#3-python-api)
- [项目结构](#项目结构shop-部分)
- [核心数据模型](#核心数据模型)
- [端到端示例](#端到端示例-复制可跑)
- [反爬策略](#反爬策略-stealthfetcher)
- [价格监控流程](#价格监控流程)
- [端到端演示](#端到端演示-无需网络)
- [测试](#测试)
- [Troubleshooting](#troubleshooting常见问题与对策)
  - [A. 安装/依赖](#a-安装依赖)
  - [B. 抓取结果为空](#b-抓取结果为空)
  - [C. 数据库](#c-数据库)
  - [D. 价格监控/告警](#d-价格监控告警)
  - [E. 反爬/限速](#e-反爬限速)
  - [F. 导出/搜索](#f-导出搜索)
- [边界与异常场景](#边界与异常场景edge-cases)
  - [E1. 价格字段缺失或异常](#e1-价格字段缺失或异常)
  - [E2. 搜索/列表为空](#e2-搜索列表为空)
  - [E3. 反爬触发后的重试](#e3-反爬触发后的重试)
  - [E4. 时间戳与时区](#e4-时间戳与时区)
  - [E5. Watchlist 配置错误](#e5-watchlist-配置错误)
  - [E6. 数据导出边界](#e6-数据导出边界)
  - [E7. SQLite 模式](#e7-sqlite-模式mac--本地无-mysql)
- [法律与伦理约束](#法律与伦理约束)
- [平台抓取难度评估](#平台抓取难度评估)
- [Pitfalls](#pitfalls踩坑提示)
- [添加新平台](#添加新平台3-步)
- [上线前验证清单](#上线前验证清单validation--test-checklist)
  - [V1. 单元测试全绿](#v1-单元测试全绿)
  - [V2. 离线 E2E 自检](#v2-离线-e2e-自检无需网络30-秒)
  - [V3. 数据契约校验](#v3-数据契约校验schema-sanity)
  - [V4. 反爬握手](#v4-反爬握手3-个真实请求1-分钟)
  - [V5. 告警回路自检](#v5-告警回路自检)
- [可观测性](#可观测性observability-tips)
  - [O1. 启用结构化日志](#o1-启用结构化日志)
  - [O2. 关键指标](#o2-关键指标放-prometheus--文本日志都行)
  - [O3. 健康检查](#o3-健康检查health-check)
  - [O4. 抓取质量巡检](#o4-抓取质量巡检)
  - [O5. 失败隔离](#o5-失败隔离不要让一次失败拖垮整批)
- [已知限制](#已知限制)
- [后续可能扩展](#后续可能扩展)
- [Anti-patterns](#anti-patterns常见错误用法)
  - [AP1–AP10](#ap1-❌-生产环境用-sqlite-替代-mysql)

**外部参考**:
- [references/quickstart.md](references/quickstart.md) — 5 分钟最小可运行示例
- [references/adapter-extension.md](references/adapter-extension.md) — 新增平台 adapter 深入指南

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

## 端到端示例 (复制可跑)

下面是一个**完整、可独立运行**的脚本,串联了"抓取 → 监控 → 趋势 → 导出"全链路。
不需要网络 — 用的 `scripts/demo_e2e.py` 同款 fixture,适合先在本地跑通再换成真实 URL。

```python
# /root/news_spider/scripts/my_full_workflow.py
# python3.8 scripts/my_full_workflow.py
import sys
sys.path.insert(0, "/root/news_spider/src")

from decimal import Decimal
from spider.shop_parsers import JdAdapter, MeituanAdapter
from spider.shop_export import export_products, ShopSearchIndex
from spider.shop_trackers import (
    PriceRepository, PriceTracker, WatchItem, PriceRecord, compute_trend,
)

# ---------- 1) 离线抓取(用 fixture HTML,真实场景换 StealthFetcher) ----------
from tests.fixtures_jd import JD_SEARCH_HTML_IPHONE       # 复用测试 fixture

adapter = JdAdapter()
products = adapter.parse_search_list(JD_SEARCH_HTML_IPHONE, "iPhone")
print(f"[1] 抓到 {len(products)} 个商品")
for p in products[:3]:
    print(f"    {p.title}  ¥{p.price}  ({p.shop_name})")

# ---------- 2) 倒排索引搜索 ----------
idx = ShopSearchIndex()
for p in products:
    idx.add(p)
hits = idx.search("iPhone")
print(f"[2] 搜索 'iPhone' 命中 {len(hits)} 个")

# ---------- 3) 加入价格监控(显式 sqlite,免 MySQL 依赖) ----------
repo = PriceRepository("/tmp/shop_demo.db")               # 显式路径 = sqlite
repo.save(PriceRecord(platform="jd", sku_id="100012345",
                      price=Decimal("5999"), in_stock=True))

# 自定义取价回调 — 生产里换成 StealthFetcher 抓详情页
def fetch_price(platform: str, sku_id: str) -> PriceRecord:
    return PriceRecord(platform=platform, sku_id=sku_id,
                       price=Decimal("5499"), in_stock=True)   # 模拟降价

tracker = PriceTracker(repo, fetch_price)
alerts = tracker.check_all([
    WatchItem(platform="jd", sku_id="100012345", threshold_pct=0.05,
              title="iPhone 15 Pro"),
])
print(f"[3] 告警: {alerts}")                                # 触发降价 8.3%

# ---------- 4) 查历史 + 趋势预测 ----------
history = repo.history("jd", "100012345", days=30)
trend = compute_trend(history)
print(f"[4] 趋势: {trend.direction}  下期预测 ¥{trend.forecast_next}  "
      f"斜率 {trend.slope:.4f}/天")

# ---------- 5) 导出 ----------
export_products(products, "/tmp/products.json", fmt="json", compress=True)
print(f"[5] 已导出 /tmp/products.json.gz")
```

**预期输出:**
```
[1] 抓到 3 个商品
    Apple iPhone 15 Pro 256GB  ¥5999.00  (京东自营)
    ...
[2] 搜索 'iPhone' 命中 3 个
[3] 告警: [{'sku_id': '100012345', 'old': '5999', 'new': '5499', 'drop_pct': 0.0833}]
[4] 趋势: down  下期预测 ¥5499.00  斜率 -0.0167/天
[5] 已导出 /tmp/products.json.gz
```

**换成真实抓取** 只需把第 1 步换成:
```python
from spider.shop_fetchers import StealthFetcher
with StealthFetcher(min_interval=2.0, max_interval=4.0) as sf:
    resp = sf.get("https://search.jd.com/Search?keyword=iPhone&page=1")
    products = JdAdapter().parse_search_list(resp.text, "iPhone")
```
第 3 步的 `fetch_price` 改成 `sf.get(detail_url)` + `parse_product_detail()` 即可。

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

> 想从零跑通整个链路,看 [references/quickstart.md](references/quickstart.md);要新增平台/扩展 adapter,看 [references/adapter-extension.md](references/adapter-extension.md)。

## Troubleshooting(常见问题与对策)

按错误现象分类,先看现象,再跳到对应章节。

### A. 安装/依赖

| 现象 | 原因 | 修复 |
|---|---|---|
| `ModuleNotFoundError: bs4` | 缺 HTML 解析库 | `pip install beautifulsoup4 lxml` |
| `ModuleNotFoundError: sqlalchemy` / `pymysql` | 缺 ORM / MySQL 驱动 | `pip install sqlalchemy pymysql cryptography` |
| `ModuleNotFoundError: playwright` 且淘宝/拼多多空结果 | 缺无头浏览器 | `pip install playwright && playwright install chromium` |
| `ImportError: /root/news_spider/src` 找不到 | 没插路径 | `sys.path.insert(0, "/root/news_spider/src")` |

### B. 抓取结果为空

| 现象 | 原因 | 修复 |
|---|---|---|
| 京东抓 0 条 | 触发了风控(IP 进黑名单) | 改大 `StealthFetcher(min_interval=3.0, max_interval=6.0)`,或换 IP/代理 |
| 京东只抓到部分,价格全是空 | `_extract_json_prices` 没匹配到 `pageData` | 拉 HTML 看 `<script>` 是否被改,可能京东已更新页面结构,需更新 parser |
| 淘宝/拼多多空 list | 列表页纯 JS 渲染 | 用 Playwright fetcher(见已知限制),或抓搜索建议接口 mtop 兜底 |
| 美团商家字段全空 | SVG 矢量文字(防爬) | 评分/价格在 `<text>` 里,需要 OCR(本版本未实现) |
| HTTP 418 / 429 | 限速不够 | 立刻停止 30 分钟,再降速到 5s+ |

### C. 数据库

| 现象 | 原因 | 修复 |
|---|---|---|
| `Can't connect to MySQL on 'localhost'` | MySQL 没启 / 端口错 | `systemctl status mysql`;检查 `.env` 的 `SHOP_DATABASE_URL` |
| `Unknown database 'shop_spider'` | 库没建 | `mysql -uroot -e "CREATE DATABASE shop_spider DEFAULT CHARSET utf8mb4"`;首次运行 ORM 会自动建表 |
| `pymysql.err.OperationalError: (1045, ...)` | 密码错 / 没权限 | 改 `.env` 里的 `SHOP_DATABASE_URL=mysql+pymysql://user:pwd@host:3306/shop_spider?charset=utf8mb4` |
| 想临时跑离线 demo 但不想装 MySQL | 显式传 sqlite 路径 | `PriceRepository("/tmp/demo.db")`(注意:仅单进程安全) |
| 写库乱码 | 表/库不是 utf8mb4 | `ALTER DATABASE shop_spider DEFAULT CHARACTER SET utf8mb4` |

### D. 价格监控/告警

| 现象 | 原因 | 修复 |
|---|---|---|
| `track` 跑完没有告警 | 当前价没跌过阈值 | 调小 `threshold_pct`(0.05 = 5%);或先手动 `save` 一条高价 record 再跑 |
| `history` 返回空 | 没历史数据 | 至少先 `tracker.check_all()` 跑过一次入库 |
| 趋势 `slope=0` | 不足 2 个数据点 | 至少 3 天数据;`compute_trend` 要求 `len(history) >= 2` |
| 告警回调没触发 | 没传 `on_alert` | `tracker.check_all(items, on_alert=my_callback)`(默认只 `print`) |
| 监控重复入库 | 同一 ts 多次 | 唯一键 `(platform, sku_id, ts)` 已防重;若还重复,检查系统时钟 |

### E. 反爬/限速

- **症状**:突然 0 结果 + HTTP 403/429/418。
- **第一步**:立刻停抓 ≥30 分钟(继续打只会延长封禁)。
- **第二步**:降速 `min_interval=4.0, max_interval=8.0`,单次会话上限 100 请求。
- **第三步**:换 IP(代理池/家庭宽带重启光猫/移动蜂窝)。
- **第四步**:换 UA(默认 Mobile 池已有 6 个,实在不行手动加 `custom_uas=[...]`)。
- **禁用项**:不要并发开多进程抓同一平台,会指数级提高被封概率。

### F. 导出/搜索

| 现象 | 修复 |
|---|---|
| CSV 中文乱码 | 用 `format=csv` 内部已 utf-8-sig;若 Excel 打开乱码,用 `pandas.read_csv(..., encoding='utf-8-sig')` |
| gzip 文件解不开 | `export_products(..., fmt="json", compress=True)` 写出的是 `.json.gz`,`gunzip -k xxx.json.gz` |
| 倒排索引查单字无结果 | 中文用 2-gram,搜词至少 2 字(避免噪声) |

## 边界与异常场景(Edge Cases)

明确框架在以下场景的**行为**和**处理建议**,避免静默失败。

### E1. 价格字段缺失或异常
- **`price == None` 或 `Decimal("0")`**:Parser 会跳过该商品,不会入库;在 watchlist 里这种 SKU `track` 会报 `ValueError: invalid price`,请在 `fetch_price` 回调里返回 `in_stock=False` 即可。
- **`original_price` 缺失**:导出时留空,`compute_trend` 不受影响(只用 `price`)。
- **价格用分而不是元**:淘宝/拼多多已自动归一;但**用户自定义 `fetch_price`** 必须自己保证单位是元(Decimal 字符串),不要传整数分。

### E2. 搜索/列表为空
- 京东搜索词**无结果**(纯噪声词):返回 `[]`,不报错。CLI `--pages 0` 会立刻退出。
- 关键词含特殊字符(`&`/`?`/`%`):URL 编码由 `search_urls()` 处理,但结果可能跳到默认搜索。
- 美团**未指定 city**:用 `meituan --city` 默认值,可能拿到错误的本地站;`MeituanAdapter.search_urls` 需要 city code 字典映射,不在表里的城市会抛 `KeyError`。

### E3. 反爬触发后的重试
- `StealthFetcher` **不内置重试**(避免放大风控)。如需重试,外层包:
  ```python
  for attempt in range(3):
      try:
          resp = sf.get(url, timeout=10)
          if resp.status_code == 200: break
      except Exception as e:
          if attempt == 2: raise
          time.sleep(30 * (attempt + 1))
  ```
- **重试前必须 sleep ≥30s**,否则必封。

### E4. 时间戳与时区
- 所有 `PriceRecord.ts` 在存储层统一 **ISO 8601 + UTC**(框架已转换)。
- **不要**直接传 `time.time()`(本地时区)给 `PriceRecord.ts`,会落库成 1970。

### E5. Watchlist 配置错误
- 缺字段:`WatchItem(...)` 会抛 `TypeError`,请检查 `--threshold` 是否传了 0~1 浮点。
- SKU 不存在:`track` 不会报错,但 `PriceRepository.history()` 返回空;用 `cli history --platform X --sku-id Y` 验证。
- **大批量监控**(>500 条):`check_all` 是顺序执行,1.5-3.5s × N ≈ 12-30 分钟,确保 cron 周期够长。

### E6. 数据导出边界
- `export_products(products, "x.json", fmt="json")`:若 `products=[]` 会写出 `[]`(合法空文件,不是错误)。
- `compress=True` + `fmt="csv"` 组合合法,产物是 `.csv.gz`。
- **不要**对同一文件并发 `export_products` 写两次,会交错。

### E7. SQLite 模式(Mac / 本地无 MySQL)
- 显式 `PriceRepository("path.db")` 才会用 SQLite。
- SQLite 模式**单进程安全**;并发写需加锁或换 MySQL。
- demo 跑完记得 `repo.close()`,否则 Windows 上文件锁住。

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

## 上线前验证清单(Validation / Test Checklist)

> 每次升级 parser、换存储后端、改 `StealthFetcher` 限速,或首次接入新平台,**跑完下面 5 步再上生产**。
> 任何一步 FAIL,直接回滚,不要带病上 cron。

### V1. 单元测试全绿

```bash
cd /root/news_spider
python3.8 -m pytest tests/ -q --tb=short
# 期望: 276 passed, 0 failed, 0 error
```

- 任意失败 → 不要上;**parser 改动尤其要看 test_xxx_parser.py 5 个 case**(列表/详情/空 HTML/缺字段/多页)。
- 关键统计: 京东 22 / 淘宝 26 / 美团 30 / 拼多多 21 / 反爬 17 / 价格监控 21 / 导出 18 / 搜索 4 / 28 models。

### V2. 离线 E2E 自检(无需网络,30 秒)

```bash
python3.8 scripts/demo_e2e.py
```

期望输出末尾 `✅ 全部链路 OK`;若停在某步,问题在该步模块:

| 停在步骤 | 大概率问题 |
|---|---|
| `[1/5] 多平台抓取` | parser 或 fixture 损坏(对比 `git diff tests/fixtures_*.py`) |
| `[2/5] 全文搜索` | `ShopSearchIndex` 倒排逻辑回归 |
| `[3/5] 倒排索引` | 中文 2-gram 分词边界改动 |
| `[4/5] 美团商家+团购` | `MeituanAdapter` 解析路径变化 |
| `[5/5] 价格监控` | `PriceTracker` 或 `compute_trend` 改动 |

### V3. 数据契约校验(Schema Sanity)

```python
# scripts/validate_orm.py — 上线前跑一次,确认 MySQL 表结构 + 关键约束
import sys; sys.path.insert(0, "/root/news_spider/src")
from decimal import Decimal
from spider.shop_models import Product, PriceRecord, WatchItem
from spider.shop_trackers import PriceRepository

repo = PriceRepository()  # 走 MySQL
# 1) 必填字段 + 类型
p = Product(platform="jd", sku_id="999", title="t", url="https://x",
            price=Decimal("1.00"))
print("Product OK:", p.to_dict()["price"])
# 2) Decimal 精度
assert str(PriceRecord(platform="jd", sku_id="1",
                       price=Decimal("0.01")).price) == "0.01"
# 3) 写读一次(确认 ORM 通)
repo.save(PriceRecord(platform="jd", sku_id="validate", price=Decimal("1")))
print("MySQL OK; n_history =", len(repo.history("jd", "validate", days=1)))
```

FAIL 信号:`Unknown database 'shop_spider'` → 跑建库 SQL(见 Troubleshooting C);`IntegrityError` → 旧数据和新 schema 冲突,先 `DROP TABLE` 再自动重建(只 demo 库,生产别 drop)。

### V4. 反爬握手(3 个真实请求,1 分钟)

```bash
# 短冒烟: 不入库,只看 HTTP 状态
python3.8 -c "
import sys; sys.path.insert(0, '/root/news_spider/src')
from spider.shop_fetchers import StealthFetcher
with StealthFetcher() as sf:
    for plat, url in [
        ('jd', 'https://search.jd.com/Search?keyword=test&enc=utf-8'),
        ('tb', 'https://s.taobao.com/search?q=test'),
        ('pdd', 'https://mobile.yangkeduo.com/search_result.html?search_key=test'),
    ]:
        r = sf.get(url, timeout=10)
        print(f'{plat:4s} status={r.status_code}  len={len(r.text)}')"
```

期望: 三个 `status=200`,`len > 5000`(京东首页是 200k+,淘宝是 50k+)。**任一返回 418/403 → IP 已进黑名单**,立刻停手,等 ≥30 分钟再降速到 5s+(见 Troubleshooting E)。

### V5. 告警回路自检

```python
# 至少跑 1 次,确认回调真的被调用
def my_alert(item, old, new):
    print(f"[ALERT] {item.sku_id} {old}->{new}")

tracker.check_all(
    [WatchItem(platform="jd", sku_id="test", threshold_pct=0.01)],
    on_alert=my_alert,
)
```

- 第一次跑没告警属正常(没历史);**手动 `save()` 一条高价,再跑** → 必出告警(参见 Troubleshooting D)。
- 邮件/微信回调接错(回调抛异常不会重试),务必先 `try/except` 包回调,避免污染 `tracker.check_all` 主流程。

## 可观测性(Observability Tips)

> 出问题后能**快速定位**比什么都重要。框架默认 `print` + `logging.INFO`,下面给最小可用的可观测性方案。

### O1. 启用结构化日志

```python
# scripts/my_crawl.py
import logging, sys
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
# spider.* logger 全部走这一条
log = logging.getLogger("shop_crawl")
log.info("start platform=%s keyword=%s", "jd", "iPhone")
```

**建议至少打**:
- 每次 HTTP 请求:`platform=... url=... status=... latency_ms=... bytes=...`
- 每次解析:`platform=... keyword=... n_items=... skipped=...`
- 每次告警:`platform=... sku=... old=... new=... drop_pct=...`
- 入库失败:`platform=... sku=... err=...`(**必须** ERROR 级)

### O2. 关键指标(放 Prometheus / 文本日志都行)

| 指标 | 类型 | 含义 | 告警阈值建议 |
|---|---|---|---|
| `shop_crawl_requests_total{platform,status}` | counter | 抓取次数 | status=429/418 占比 >5% |
| `shop_crawl_items_total{platform}` | counter | 解析得到商品数 | 突降 50% 持续 30min |
| `shop_crawl_latency_seconds{platform}` | histogram | 单次请求耗时 | p95 > 10s |
| `shop_price_alerts_total{platform}` | counter | 告警次数 | 任意突增 |
| `shop_db_write_seconds` | histogram | 写库耗时 | p95 > 1s |
| `shop_parse_skipped_total{platform,reason}` | counter | 跳过商品 | missing_price >30% |

最简实现: 业务代码里 `log.info("crawl", extra={...})`,grep 日志聚合。
真要接 Prometheus:加 `prometheus_client`,在 `StealthFetcher.__exit__` / `PriceTracker.check_all` 末尾 `inc()`。

### O3. 健康检查(Health-check)

```python
# scripts/healthcheck.py  — cron 每 5 分钟跑
import sys; sys.path.insert(0, "/root/news_spider/src")
from spider.shop_trackers import PriceRepository
from decimal import Decimal
from datetime import datetime, timezone, timedelta

repo = PriceRepository()
# 1) MySQL 联通
n = len(repo.history("jd", "__healthcheck__", days=1))  # 一定空
print(f"[OK] mysql reachable")
# 2) 24h 内有数据?告警链路是否健康
yesterday = datetime.now(timezone.utc) - timedelta(days=1)
n_recent = repo.count_since(yesterday)  # 若 ORM 没此方法,自己用 SELECT COUNT
if n_recent == 0:
    print(f"[WARN] no records in last 24h, track cron may be down")
```

cron: `*/5 * * * * /usr/bin/python3.8 /root/news_spider/scripts/healthcheck.py | mail -s "shop-spider health" you@example.com`

### O4. 抓取质量巡检

定期(每天/每周)检查:
- 同一 SKU 两次抓的价格差 > 30%?可能是 parser bug 或商家改价
- `parse_skipped_total{reason="missing_price"}` > 30%?HTML 结构改了
- 新增商品数 = 0 持续 N 天?search_url 失效或被风控

### O5. 失败隔离(不要让一次失败拖垮整批)

```python
# 列表解析里包 try/except(参考 adapter-extension.md §4)
for el in items:
    try:
        products.append(self._parse_one(el, keyword))
    except (ValueError, AttributeError) as e:
        log.warning("parse_skip sku=%s err=%s", el.get("data-sku"), e)
        continue  # 缺字段静默跳过,不要 raise
```

**核心原则**: parse 失败只丢一条;fetch 失败影响整批,务必记 ERROR 日志 + 降速重试。

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

## Anti-patterns(常见错误用法)

> 以下是真实项目中反复出现过的**反模式**。每条都标注后果,踩坑前请先扫一遍。

### AP1. ❌ 生产环境用 SQLite 替代 MySQL
- **错**: `repo = PriceRepository("shop.db")` 写到 cron 任务里长期运行。
- **后果**: SQLite **单进程写锁**;多 worker / 多次 cron 触发立刻 `database is locked`;丢历史数据。
- **对**: 生产固定 `PriceRepository()`(无参),走 MySQL;SQLite 只在 `scripts/demo_e2e.py` / 单次离线脚本用。

### AP2. ❌ 关闭限速追求"更快"
- **错**: `StealthFetcher(min_interval=0.0, max_interval=0.1)` 或自行绕过 `HttpFetcher`。
- **后果**: 5 分钟内 IP 进黑名单,后续 24h 全部 403;**降速没用,只能换 IP**。
- **对**: 默认 1.5-3.5s 已经是底线,绝不要再低。京东/拼多多要求 ≥3s。

### AP3. ❌ 并发多进程抓同一平台
- **错**: `multiprocessing.Pool(8).map(crawl_jd, keywords)`。
- **后果**: 8 个并发连接同 IP → 100% 触发风控,且 StealthFetcher 的 session 限速失效。
- **对**: 单进程顺序抓;真要加速用**不同 IP 池**(代理/蜂窝),每个 IP 一个进程。

### AP4. ❌ 用 `fetch_price` 回调直接返回硬编码价格
- **错**: 在测试脚本写死 `Decimal("99")` 然后跑 `track` 入生产库。
- **后果**: 历史价格被假数据污染,趋势预测全错,**且无法回滚**。
- **对**: `fetch_price` 必须从真实数据源(详情页 API/商家后台)取;fake 只在 `tmp sqlite` demo 里用。

### AP5. ❌ 抓登录后才能看到的页面(订单/评论详情/会员价)
- **错**: 用 cookie 池/打码平台绕过登录拿评论。
- **后果**: 违反各平台 ToS 与个人隐私法规(PIPL/GDPR);本 skill 已在 trigger 排除,**不要再用本框架绕**。
- **对**: 公开页面够用就好;评论要做分析请用平台官方开放 API。

### AP6. ❌ 把爬到的数据上传到第三方或商业再分发
- **错**: 抓到的商品图/标题/价格做成公开比价网站 / 转卖数据库。
- **后果**: 平台发律师函 / IP 永久封禁 / 法律风险。
- **对**: 仅供**个人分析/学习**;本地落库,绝不外传(见 法律与伦理约束 一节)。

### AP7. ❌ 用整数(分)直接传 PriceRecord
- **错**: `PriceRecord(..., price=599900)`(以分为单位)。
- **后果**: 落库后趋势/告警全按 599900 元计算,触发假"降价 99%"误报。
- **对**: 永远传 `Decimal("5999.00")` 字符串元;淘宝/拼多多 parser 已自动转换,但**自定义回调自己负责**。

### AP8. ❌ 给同一 SKU 设两个不同阈值的 WatchItem
- **错**: `watchlist.json` 里同一个 `jd/100012345` 出现两次,阈值分别是 0.05 和 0.20。
- **后果**: 重复入库 + 重复告警;`PriceTracker.check_all` 不去重,DB 唯一键只防**完全相同 ts**,不同 ts 还是会双倍。
- **对**: 一个 SKU 一条;要分级告警在 `on_alert` 回调里分支。

### AP9. ❌ 在 watchlist 写"等降价就买"的交易逻辑
- **错**: 收到告警回调自动下单。
- **后果**: 这不是交易框架;无订单管理/库存校验/支付;且"降价"≠"好价"。
- **对**: 告警只做**通知**(邮件/微信),让用户**手动**决策。

### AP10. ❌ 不读 parser 源码就改 `_extract_json_prices` 等私有函数
- **错**: 直接 monkey-patch 私有方法,绕过 `__post_init__` 校验。
- **后果**: 下次升级被覆盖,且脏数据混进 MySQL 难以清理。
- **对**: 扩展走 **Adapter 子类**或新增 `parse_product_detail`,改 parser 提 PR。完整流程见 [references/adapter-extension.md](references/adapter-extension.md)。

## 另请参阅(See also)

- [references/quickstart.md](references/quickstart.md) — 5 分钟最小可运行示例,适合"先跑起来再说"
- [references/adapter-extension.md](references/adapter-extension.md) — 新增平台(1688/亚马逊/苏宁)时的完整 adapter 实现指南,含 selector 踩坑 / 价格单位归一 / fixture 模板

**本 skill 内的相关章节锚点**:
- 出问题先看 [Troubleshooting](#troubleshooting常见问题与对策),再跳到 [Edge cases](#边界与异常场景edge-cases)
- 上线前必跑 [Validation / Test Checklist](#上线前验证清单validation--test-checklist)(V1–V5)
- 接入监控/Prometheus 体系看 [Observability Tips](#可观测性observability-tips)(O1–O5)
- 改 parser 或换存储后端,先扫 [Anti-patterns](#anti-patterns常见错误用法)(AP1–AP10)
