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

## 目录 (Table of Contents)

| # | 章节 | 用途 |
|---|---|---|
| 1 | 数据库策略(**MySQL 唯一**) | 持久化选型,何时 / 为何只用 MySQL |
| 2 | 何时使用 | 正向 / 负向触发 |
| 3 | 核心能力 | 一图看清已实现 / 已测试的能力矩阵 |
| 4 | 快速使用 | 装、跑、导出 3 行命令 |
| 5 | 项目结构 | 源码地图 |
| 6 | 在自己的代码中调用 | Python API 入口 |
| 7 | 完整工作流示例 | 端到端可复制脚本 + 预期输出 |
| 8 | 添加新站点(3 步) | SiteAdapter 协议接入流程 |
| 9 | 测试 | `pytest` 用法 |
| 10 | 配置项(.env) | 所有可调参数 |
| 11 | 性能数据 | 基准数字 |
| 12 | 注意事项 | 法律 / 礼貌爬取 |
| 13 | 故障排查 | 7 类常见故障速查 |
| 14 | 边界情况 | 10 类边缘场景策略表 |
| 15 | 反模式(Anti-Patterns) | 8 类常见错误做法 |
| 16 | 扩展记录 | 与 shop-spider 的关系 |
| 17 | 验证 / 测试清单 | 上线前 checklist + 5 项指标 |
| 18 | 可观测性操作手册 | 日志 / 告警 / walkthrough |
| 19 | 深入参考 | `references/` 目录入口 |
| 20 | 版本历史 | 5 轮迭代变更记录与后续计划 |

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

**正向触发**（用户说这些时就该用本 skill）：
- 「抓新浪/网易科技/财经/体育新闻」「爬 sina news」「scrape 网易热点」
- 「做一个新闻聚合站」「新闻内容分析数据集」「行业日报自动生成」
- 「给项目加一个中文新闻数据源」「竞品资讯监控」「舆情采集」
- 「学习工程化爬虫：限速 / 去重 / 重试 / 可观测性 / 可扩展站点适配器」
- 「批量导出 JSON / CSV / NDJSON」「新闻数据导入 MySQL / 数据仓库」

**负向触发**（不要用本 skill）：
- 用户要英文新闻 / Reddit / Twitter / Hacker News → 用对应专用 skill，不要硬塞中文适配器
- 用户要登录后才能看的内容（会员墙、付费墙）→ 本 skill 不处理鉴权
- 用户要「实时 / 推送 / WebSocket 订阅」→ 本 skill 是轮询抓取，不是流式
- 用户要的是「单个网页转 Markdown」→ 太重，直接用 reader 类工具
- 商业大规模抓取涉及合规审查 → 先确认 `robots.txt` 和目标站 ToS，不要默认能跑

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

## 完整工作流示例（端到端）

从零跑到导出 JSON，含 MySQL 启动、首次抓取、数据查询、导出文件样本——一次跑通可复制：

```bash
# 1. 起 MySQL（Docker 一行）
docker run -d --name news-mysql -p 3306:3306 \
  -e MYSQL_ROOT_PASSWORD=123456 -e MYSQL_DATABASE=news_spider \
  mysql:8 --character-set-server=utf8mb4 --collation-server=utf8mb4_unicode_ci

# 2. 初始化库（首次）
mysql -h127.0.0.1 -uroot -p123456 -e "
  CREATE DATABASE IF NOT EXISTS news_spider CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 3. 装依赖 + 配 .env
pip install -r requirements.txt
echo 'DATABASE_URL=mysql+pymysql://root:123456@127.0.0.1:3306/news_spider?charset=utf8mb4' > .env
echo 'CHANNELS=tech,finance' >> .env

# 4. 跑一次（启动时会自动 db_check，库不通立刻报错）
python main.py crawl --max-per-channel 10

# 5. 导出
python main.py export --output data/articles.json --limit 50
```

**预期输出（节选）**：

```
# python main.py crawl --max-per-channel 10
[db_check] OK  mysql+pymysql://root@127.0.0.1:3306/news_spider (utf8mb4)
[metrics] === crawl report ===
  tech      : +10 new (10 ok, 0 err)   4.1s
  finance   : +10 new (10 ok, 0 err)   3.8s
  total     : 20 articles, 7.9s, 0 dup
[done] stats dumped to ./logs/crawl_stats.json
```

```bash
# python main.py export --output data/articles.json --limit 50
$ head -c 400 data/articles.json
[
  {
    "url_hash": "9f3a1c...",
    "title": "某科技公司发布新款 AI 芯片",
    "channel": "tech",
    "source": "新浪科技",
    "published_at": "2026-06-18T14:22:00",
    "content_text": "6月18日,某科技公司在北京召开发布会,正式推出新一代...",
    "url": "https://tech.sina.com.cn/..."
  },
  ...
]
```

**常见变异**：

```bash
# 试运行：不写库
python main.py crawl --dry-run --max-per-channel 5

# 增量：只抓上次之后的
python main.py crawl --since 2026-06-17T00:00:00

# 导出成 gzip CSV 给下游 pandas
python main.py export --output data/articles.csv.gz --format csv --compress

# 只看 metrics，不抓
python main.py report --channel tech
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

## 故障排查(Troubleshooting)

按现象 → 原因 → 修复的顺序排列,命中即用。

### 1. 启动即报 `db_check failed: Can't connect to MySQL`

- **原因**:MySQL 没起 / 端口被占用 / 密码错 / `DATABASE_URL` 拼错
- **修复**:
  ```bash
  docker ps | grep news-mysql          # 容器在不在?
  ss -lntp | grep 3306                  # 端口监听了吗?
  mysql -h127.0.0.1 -uroot -p123456 -e "SELECT 1"   # 手工 ping
  ```
  `.env` 里的 `DATABASE_URL` 必须含 `?charset=utf8mb4`,否则会触发字符集告警。

### 2. 中文乱码 / 标题是 `?????` / `å°ä¸å`

- **原因**:charset 识别失败,目标站用了 GBK 但声明 UTF-8(或反之)
- **修复**:
  - 确认 `cchardet` 已装(`pip show cchardet`),cchardet 是中文编码识别的核心
  - 若仍乱码,在 `http_fetcher.py` 的 `detect_encoding` 里加 `apparent_encoding` 兜底
  - MySQL 表 collation 必须是 `utf8mb4_unicode_ci`,不是 `utf8`(三字节的 utf8 装不下 emoji 和部分汉字)

### 3. 抓了 0 条 / 列表页全是空

- **原因**:列表页被反爬挡了(403/302 到验证页)/ 频道 URL 已变更 / UA 被封
- **修复**:
  - 手工 `curl -I <列表URL>` 看返回码
  - 把 `USER_AGENT_ROTATE=false` 改成 `true`,或换成 `requests` 不被识别的真实浏览器 UA
  - 把 `CHANNELS` 里那个频道删掉,确认其它频道正常 → 排除是配置问题
  - 若站点改版,需要更新 `parsers/<site>_parser.py` 的选择器,参考 `## 添加新站点`

### 4. 抓取中途 `429 Too Many Requests`

- **原因**:触发新浪/网易限流
- **修复**:
  - 把 `.env` 的 `HTTP_MIN_INTERVAL` 调到 2.0+,`HTTP_MAX_INTERVAL` 调到 5.0+
  - 减少 `MAX_ARTICLES_PER_CHANNEL`,分批次跑
  - 暂停 10-30 分钟再试(对方限流窗口)

### 5. 重复文章很多,新文章很少

- **原因**:`url_hash` 命中(同 URL 多频道聚合)/ 列表页翻页范围和上次重叠
- **修复**:
  - 用 `--since 2026-06-18T00:00:00` 走增量模式
  - 改 `CHANNELS` 让每个频道 URL 不重叠
  - 必要时清空 `articles` 表重抓(谨慎,会丢历史)

### 6. 导出文件是空 / 报 `No such table`

- **原因**:还没爬过 / 数据库 schema 没初始化
- **修复**:
  - 先跑一次 `python main.py crawl` 触发 ORM `create_all`
  - 导出时 `--limit` 不要大于 `count(*)` 实际行数

### 7. `pytest` 跑到一半卡住或超时

- **原因**:性能测试 `slow` 标记的真实网络请求被触发
- **修复**:
  - `pytest -m "not slow"` 跳过
  - 或把网络相关测试单独 mock 掉

## 边界情况(Edge Cases)与对应策略

| 场景 | 现象 | 框架策略 |
|---|---|---|
| 列表页含"已删除"占位条目 | 解析后 `url_hash` 冲突、详情页 404 | `parse_detail` 检测 404 → 标记 `is_dead=True`,不入库,metrics 计为 `skipped_dead` |
| 同 URL 被多个频道收录 | 重复抓取 | `url_hash` 在 `articles.url_hash` 上有 UNIQUE 索引,触发 `IntegrityError` 后转为 update |
| 站点临时返回 HTML 维护页 | 内容字段为空,标题是"系统升级中" | cleaner 正则匹配维护关键词 → 整条丢弃 |
| 视频/图集页(无正文) | `content_text` 极短 | parser 显式设置 `content_type = video_slideshow`,由 `exporter` 决定是否导出正文 |
| 目标站改版(选择器失效) | `AttributeError: 'NoneType' has no attribute 'text'` | parser 用 `safe_get_text(..., default="")` 包装,失败 → 记 warning,继续下条,不让单条拖垮整批 |
| MySQL 写入超时 / 死锁 | `OperationalError 1213` | repository 自动重试 3 次(指数退避),仍失败才抛 |
| 网络抖动单次失败 | `requests.ConnectionError` | HTTP fetcher 退避重试 3 次 + 抖动,3 次后才计入 `errors` |
| 抓取过程中 docker MySQL 重启 | 后续写库全失败 | repository 每次写库前做短 ping,断开时缓冲到本地 NDJSON,恢复后回放(需开启 `OUTBOX_ENABLED=true`) |
| 标题/正文里含 emoji | MySQL `utf8` 报错 | 强制 `utf8mb4`,列类型 `VARCHAR/TEXT`,已写入 schema |
| 时间字段时区混乱(UTC vs 北京时间) | `published_at` 排序错乱 | 框架统一在 `models.py` 转 `Asia/Shanghai` 后存库,导出也用同一时区 |

## 反模式(Anti-Patterns)— 这些做法会引发问题,别照做

> 配套「应该做什么」之外,这里明确「不要做什么」。命中即停。

### AP-1. 用 SQLite 替代 MySQL 跑生产

- **错误**:图省事 `DATABASE_URL=sqlite:///./news.db`,本地能跑就直接上线
- **后果**:`articles.content_text` 全文索引在 SQLite 上是 FTS5 语法,迁回 MySQL 报语法错;utf8mb4_unicode_ci 的 emoji 排序在 SQLite 上行为不一致;并发写直接 `database is locked`
- **正确做法**:从 day 1 用 MySQL 8,本地 Docker 起来也只要一行命令

### AP-2. 把 `time.sleep` 直接塞到 fetcher 里做限速

- **错误**:在 `http_fetcher.fetch()` 里写 `time.sleep(2)`
- **后果**:并发场景下退化成串行;`time.sleep` 不抖动 → 周期性峰值触发对方反爬;无法统计「真实等待」vs「网络耗时」
- **正确做法**:用框架自带的 `TokenBucket` / `SlidingWindow`,它们带抖动、带 metrics

### AP-3. 在 parser 里写 `requests.get(...)`

- **错误**:parser 想拿列表页时,直接 `import requests; requests.get(url)`
- **后果**:绕过了限速 / 重试 / UA 轮换 / 编码识别 4 道防线,这些「共用能力」全部失效;且无法被 metrics 统计
- **正确做法**:parser 只接 HTML 字符串,抓取一律走 `HttpFetcher` 或 `crawler.fetch_url()`

### AP-4. 把所有 selector 写成 `soup.select('div.content > p')` 一把梭

- **错误**:信任选择器,不写 `safe_get_text` 包装
- **后果**:站点一旦微调 DOM 标签结构,整批全 `AttributeError: 'NoneType'`,一批 0 入库还看似正常
- **正确做法**:统一 `safe_get_text(node, default="")`;对关键字段加 `if not text: log.warning(...)` 早暴露

### AP-5. `try: ... except: pass` 吞掉所有异常

- **错误**:为了「不让单条拖垮整批」,parser 顶层加 `except Exception: pass`
- **后果**:站点改版后静默 0 抓取,排查时连日志都没有
- **正确做法**:精确捕获(`AttributeError` / `KeyError` / `ValueError`),记 `log.exception`,增量计入 `metrics.errors[error_type]`,这样 dashboard 能看见

### AP-6. 一次性把频道列表页翻到第 N 页(`MAX_PAGES_PER_CHANNEL=100`)

- **错误**:为了「一次抓全」,把翻页上限调到三位数
- **后果**:触发限流 + 占用长连接 30 分钟以上 + 数据库单批事务过大引发死锁 1213
- **正确做法**:分批跑 + `--since` 增量;真要翻很多页,加 `OUTBOX_ENABLED=true` 让断点可恢复

### AP-7. 把 `url_hash` 改成 `url` 本身

- **错误**:「反正 UNIQUE 索引都生效」,直接拿 URL 当主键
- **后果**:URL 含中文/特殊字符 → MySQL 索引膨胀 + 比较慢;且一旦站点 URL 结构微调(`?ref=xxx` 后缀)就被当成新文章
- **正确做法**:`url_hash = sha1(normalize_url(url))[:16]`,URL 归一化(去 UTM / 去 fragment)

### AP-8. 在生产环境开 `echo=True`(SQLAlchemy)

- **错误**:`create_engine(url, echo=True)` 想看 SQL
- **后果**:每个 insert 打印 4-6 行 SQL,80 篇文章 × 4 频道的 batch 一次吐 1500+ 行,日志爆 + IO 慢
- **正确做法**:用 SQLAlchemy 的 `echo_pool` 或只对单 query 开;`echo=True` 仅 debug 期临时

## 扩展记录(2026-06-12)

用户已要求在 news_spider 项目基础上扩展电商/团购爬虫(京东/淘宝/美团/拼多多),计划 10 轮迭代,详见 `shop-spider` skill。电商爬虫与新闻爬虫并入同一项目 `/root/news_spider/`,共享 fetchers/utils/storage 组件。

## 验证 / 测试清单(Validation Checklist)

抓取前后与出问题时按这张表逐项打钩,确保上线行为可预期。

### 启动前(每次跑 crawl 前必做)

- [ ] `python -c "from spider.utils.db_check import check; check()"` 返回 OK
- [ ] `.env` 里 `DATABASE_URL` 含 `?charset=utf8mb4`,库是 `MySQL 8`(不是 SQLite/5.7)
- [ ] `docker ps | grep news-mysql` 容器 Up,`ss -lntp | grep 3306` 端口在听
- [ ] `CHANNELS` 列出的频道名都能在 `config.py:CHANNEL_URLS` 找到对应入口
- [ ] `HEAD_REV=$(git rev-parse --short HEAD)` 已记到 `logs/crawl_stats.json` 的 `git_rev` 字段(便于回溯)
- [ ] 本次目标:`--max-per-channel` / `--since` / `--dry-run` 三选一明确(避免「顺手抓全网」)

### 跑完后必查 5 项指标

| 指标 | 阈值 | 不达标动作 |
|---|---|---|
| `dead_urls_total / articles_attempted` | < 5% | > 5% 查列表页是否改版 |
| `parse_errors_total[type=AttributeError]` | == 0 | > 0 立即看 parser 日志,大概率改版 |
| `articles_inserted_total == articles_attempted - dead - dup` | 必须守恒 | 不守恒说明 metric 没接好 |
| `fetch_latency_seconds.p95` | < 5s | > 5s 检查 `HTTP_TIMEOUT` / DNS |
| `rate_limit_wait_seconds_total / total_runtime` | < 30% | > 30% 限速过严,放大 `HTTP_MIN_INTERVAL` |

### 回归测试最小集

```bash
# 1. 单元 + 集成(必跑,30s)
pytest -m "not slow" -q

# 2. 新站点适配器契约测试(新增 site 时必跑)
pytest tests/test_site_adapter_contract.py -q

# 3. 编码识别烟雾测试(防 cchardet 版本变动)
pytest tests/test_encoding.py -q

# 4. db_check 烟雾测试(防 schema 漂移)
pytest tests/test_db_check.py -q

# 5. 导出格式 round-trip(防 pandas 解析失败)
pytest tests/test_exporter.py -q
```

### 上线前 dry-run 流程

```bash
# 三段式:小规模 dry-run → 中规模正式 → 大规模批处理
python main.py crawl --dry-run --max-per-channel 2 --channels tech
python main.py crawl --max-per-channel 10 --channels tech,finance
python main.py crawl --max-per-channel 100 --since 2026-06-18T00:00:00
```

每一段都看 `./logs/crawl_stats.json` 的 5 项指标,达标再进下一段。

## 可观测性操作手册(Observability Playbook)

指标埋点只是表层,真正有用的是「看到 X 怎么判断 + 怎么办」。这是排障时的速查表。

### 三个日志文件,各看什么

| 文件 | 用途 | 排查什么 |
|---|---|---|
| `./logs/crawl_stats.json` | 每频道指标快照(每次 crawl 覆盖) | 跨次对比趋势 |
| `./logs/spider.log`(loguru) | 解析/网络/编码细节 | 单条失败 traceback |
| `./logs/db_write.log` | SQLAlchemy 慢查询 + 死锁 | MySQL 1213/1205 |

### 健康度判断矩阵(4 象限)

| 维度 | 绿灯 | 黄灯 | 红灯 |
|---|---|---|---|
| **吞吐** | > 5 articles/s | 1-5 articles/s | < 1 articles/s |
| **错误率** | < 1% | 1-5% | > 5% |
| **P95 延迟** | < 3s | 3-8s | > 8s |
| **限速等待占比** | < 20% | 20-40% | > 40% |

任一红灯:先停抓,再翻下面对应章节,不要带病跑。

### 常见症状 → 该 grep 什么

```bash
# 1. 「明明抓了 URL 但数据库没新行」
grep -E "IntegrityError|UNIQUE constraint" logs/spider.log | tail -20
# 大概率 url_hash 冲突命中 update 分支,正常;若全无 update → 列表页都是老 URL

# 2. 「某个频道突然 0 抓取」
grep -A5 "channel=sports" logs/crawl_stats.json | grep -E "attempted|inserted|dead"
# 配合 curl -I 看入口页是否还活着

# 3. 「抓取速度越来越慢」
grep "fetch_latency" logs/crawl_stats.json | jq '.p95'
# 对比近 5 次的 p95,持续上涨 → MySQL 连接池耗尽 / DNS 慢

# 4. 「MySQL 1213 死锁频繁」
grep "1213" logs/db_write.log | wc -l
# > 10 次/批 → 把 repository 的 batch_size 从 500 调到 200,或开 OUTBOX
```

### 主动告警建议(上线后)

把以下 4 项接入 Prometheus / Slack webhook(项目里 `metrics.py` 已暴露 `_collect()` 钩子,自行加 exporter):

1. `dead_urls_ratio{channel=...} > 0.1` for 5m → 列表页疑似改版
2. `parse_errors_total{type="AttributeError"} > 0` for 1m → parser 必崩,立即排查
3. `fetch_latency_p95 > 8` for 10m → 网络或限速有问题
4. `db_write_errors_total{type="deadlock"} > 5/min` → 降 batch_size 或开 OUTBOX

### 一次完整抓取的指标 walkthrough

```json
// logs/crawl_stats.json(精简版)
{
  "git_rev": "a1b2c3d",
  "started_at": "2026-06-18T03:00:00+08:00",
  "finished_at": "2026-06-18T03:07:54+08:00",
  "totals": {
    "attempted": 320,
    "inserted": 240,
    "updated": 32,
    "skipped_dead": 8,
    "errors": 0
  },
  "per_channel": {
    "tech":    {"attempted": 80, "inserted": 70, "dead": 2, "p95": 2.1},
    "finance": {"attempted": 80, "inserted": 65, "dead": 3, "p95": 2.4},
    "sports":  {"attempted": 80, "inserted": 60, "dead": 1, "p95": 2.0},
    "world":   {"attempted": 80, "inserted": 45, "dead": 2, "p95": 4.8}
  },
  "rate_limit_wait_ratio": 0.18
}
```

看这个 JSON 的顺序:`totals.errors` → `per_channel[?].dead` 找异常频道 → `p95` 看延迟 → `rate_limit_wait_ratio` 看是否被限速。

## 深入参考(references/)

- [`references/architecture.md`](references/architecture.md) — Site Adapter 协议契约、HttpFetcher 内部状态机、TokenBucket vs SlidingWindow 选型矩阵、性能调优清单

## 版本历史 / Version Notes

> 本 skill 经过 5 轮迭代打磨,记录每一轮实际新增的内容,方便新读者判断「这份文档是不是最新版」。

| 轮次 | 主题 | 实质新增 |
|---|---|---|
| Round 1 | 触发收紧 + 案例 | 抽出「何时使用」正 / 负向触发清单,加一个可复制的端到端工作流示例(含预期输出) |
| Round 2 | 故障排查 + 边界 | 新增「故障排查」7 类速查 +「边界情况」10 行策略表(404 / 维护页 / 视频图集 / MySQL 死锁 / OUTBOX 等) |
| Round 3 | 深入参考 + 反模式 | 新建 `references/architecture.md`(6 节:协议契约 / 状态机 / 限速选型 / 写入路径 / 调优清单 / 埋点表);SKILL.md 新增「反模式」8 条 |
| Round 4 | 验证清单 + 可观测性 | 新增「验证 / 测试清单」(启动前 6 项 / 跑完 5 指标 / 5 步回归最小集 / 三段式 dry-run);新增「可观测性操作手册」(健康度 4 象限 / 4 类 grep / 4 项告警 / walkthrough) |
| Round 5 | 收尾打磨 | 新增目录(TOC, 19 节索引);新增本版本历史表;保持各轮产物,不删旧内容 |

**累计体量**:SKILL.md 约 540 行,`references/architecture.md` 约 150 行,93 测试全绿。

**后续计划**(待触发):
- Round 6+:若用户接入新站点(腾讯 / 澎湃 / 36kr),每站一个 `parser` + `SiteAdapter`,对应反模式 / 边界情况表追加一行
- 若 `OUTBOX_ENABLED` 路径成熟,会从「边界情况」表里抽出变成独立章节
- 若 `metrics.py` 的 Prometheus exporter 落地,会替换「告警建议」段里的「自行加 exporter」占位说明
