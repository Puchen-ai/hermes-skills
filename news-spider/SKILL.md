---
name: news-spider
description: |
  鲁棒的中文新闻爬虫框架,内置新浪/网易两个站点。完整工作流包括:
  HTTP 抓取(带重试+限速+UA 轮换+中文编码自动识别)、
  HTML 解析(列表页+详情页+视频页+图集页+404 检测)、
  数据清洗(广告/来源/责编等 15+ 元数据自动过滤)、
  MySQL 持久化(项目默认数据库,SQLAlchemy ORM,utf8mb4)、
  启动前自检(db_check 工具,确保 MySQL 可达)、
  导出(JSON/CSV/NDJSON,支持 gzip)、
  可观测性(每频道成功率/吞吐/耗时统计)、
  Site Adapter 协议(新增站点只需 1 个文件)。
  触发场景:用户想抓取中文新闻、构建新闻聚合、做内容分析、采集竞品资讯。
---

# News Spider Skill

一个生产级的中文新闻爬虫框架,93 个测试全绿,直接可用。

## 数据库策略（**MySQL 唯一**）

本项目**默认且强制使用 MySQL 8** 作为持久化后端，**SQLite 不再是合法选项**。

| 场景 | 推荐 |
|---|---|
| 本地开发 / 沙箱 | MySQL 8 + utf8mb4 |
| 生产部署 | MySQL 8 + utf8mb4 |
| 单元测试 / 临时 demo | MySQL（用 Docker 一行起） |
| 真·离线场景 | 显式传 sqlite 路径给 `PriceRepository`（仅 `shop-spider`，news 不支持） |

**原因**：news-spider 用 SQLAlchemy ORM，本来就跨库，但项目从 2026-06-15 起把 MySQL 定为唯一存储，避免"开发用 SQLite、生产用 MySQL"导致的两边数据/字段类型不一致。

## 何时使用

- 抓取新浪/网易新闻(科技/财经/体育/国际/娱乐/军事)
- 批量采集竞品资讯、行业动态
- 构建新闻聚合站、内容分析数据集
- 学习爬虫工程化(限速/去重/监控/可扩展)
- 给已有项目加一个新闻数据源

## 核心能力(都已实现并测试)

| 能力 | 实现 | 测试 |
|---|---|---|
| HTTP 抓取 + 重试 + 限速 + UA 轮换 | ✅ | ✅ |
| 中文编码自动识别(UTF-8/GBK/GB18030) | ✅ | ✅ |
| 列表/详情/视频/图集/404 五种页面 | ✅ | ✅ |
| url_hash 去重 + 批量 upsert(4447/s) | ✅ | ✅ |
| 广告/元数据 15+ 模式过滤 | ✅ | ✅ |
| JSON/CSV/NDJSON 导出 + gzip | ✅ | ✅ |
| 多站点(SiteAdapter 协议) | ✅ | ✅ |
| 每频道 metrics 报告 | ✅ | ✅ |
| TokenBucket 令牌桶限速 | ✅ | ✅ |
| SlidingWindow 滑动窗口限速 | ✅ | ✅ |

## 快速使用

```bash
# 安装
pip install -r requirements.txt

# 抓取
python main.py crawl --max-per-channel 20

# 导出
python main.py export --output data/articles.json --limit 100
python main.py export --output data/articles.csv --format csv --compress
```

## 项目结构

```
src/spider/
├── config.py            pydantic-settings 配置
├── models.py            Article 数据类
├── crawler.py           编排器
├── metrics.py           统计收集
├── site_adapter.py      站点适配器协议
├── exporter.py          JSON/CSV/NDJSON
├── fetchers/
│   └── http_fetcher.py  requests + retry + rate limit
├── parsers/
│   ├── sina_parser.py   新浪(列表+详情+视频+图集+404)
│   └── netease_parser.py 网易
├── storage/
│   ├── models.py        SQLAlchemy ORM
│   └── repository.py    仓库
└── utils/
    ├── logger.py        loguru
    ├── cleaner.py       文本清洗
    ├── rate_limiter.py  TokenBucket + SlidingWindow
    └── user_agents.py   UA 轮换
```

## 在自己的代码中调用

```python
import sys
sys.path.insert(0, '/path/to/news_spider/src')

from spider.crawler import Crawler

crawler = Crawler(headless=False)
try:
    stats = crawler.crawl_all(max_articles_per_channel=20)
    for s in stats:
        print(f"{s['channel']}: +{s['inserted']} new, {s['errors']} errs")
    # See detailed metrics
    print(crawler.metrics.report())
finally:
    crawler.close()

# Read data
from spider.storage.repository import ArticleRepository
repo = ArticleRepository()
recent = repo.list_recent(limit=10, channel="tech")
for a in recent:
    print(a['title'], a['url'])
```

## 添加新站点(3 步)

1. **写 parser** — 仿 `netease_parser.py`
2. **写 list URL** — 加到 `config.py:CHANNEL_URLS`
3. **写 SiteAdapter** — 实现 `list_urls` / `parse_list` / `parse_detail`

## 测试

```bash
pytest                    # 93 passed in 15s
pytest -m "not slow"      # skip performance
pytest --cov=src/spider   # coverage
```

## 配置项(.env) — MySQL 必填

```ini
# 主库 (新闻文章 + 爬取日志) — MySQL 必填
DATABASE_URL=mysql+pymysql://root:123456@127.0.0.1:3306/news_spider?charset=utf8mb4

# 独立库 (电商价格历史) — 必填
SHOP_DATABASE_URL=mysql+pymysql://root:123456@127.0.0.1:3306/shop_spider?charset=utf8mb4
```

驱动: `pymysql` (纯 Python, 无需编译, Python 3.6+ 通用)。

**首次启动**：MySQL 里需要先建两个空库（utf8mb4），脚本会自检并友好报错：

```sql
CREATE DATABASE news_spider CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE shop_spider  CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
```

`main.py` 启动时会自动调 `db_check()`：库不存在/密码错/网络不通会立刻抛错并给出修复提示，不用等到爬到一半才发现。

```ini
HTTP_TIMEOUT=15
HTTP_MIN_INTERVAL=1.0       # 秒
HTTP_MAX_INTERVAL=3.0
CHANNELS=tech,finance,sports,world
MAX_PAGES_PER_CHANNEL=10
MAX_ARTICLES_PER_PAGE=20
USER_AGENT_ROTATE=true
```
```

## 性能数据

- 单条抓取: ~0.4s
- 批量 upsert: **4447 条/秒**
- 80 篇文章/4 频道完整抓取: ~30s

## 注意事项

- 严格遵守目标站 `robots.txt` 和 ToS
- 默认 1-3 秒随机间隔,礼貌爬取
- 仅供学习与个人研究,不用于商业爬取
- 视频页/图集/404 都有专门处理,不会因为页面类型变化崩

## 扩展记录(2026-06-12)

用户已要求在 news_spider 项目基础上扩展电商/团购爬虫(京东/淘宝/美团/拼多多),计划 10 轮迭代,详见 `shop-spider` skill。电商爬虫与新闻爬虫并入同一项目 `/root/news_spider/`,共享 fetchers/utils/storage 组件。
