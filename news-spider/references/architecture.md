# News Spider — Architecture Reference

深入参考文档,补充 SKILL.md 主体未展开的设计契约和选型依据。

## 1. Site Adapter 协议契约

`SiteAdapter` 是新增站点的「扩展点」。协议定义在 `src/spider/site_adapter.py`,3 个核心方法:

```python
class SiteAdapter(Protocol):
    name: str                                # 唯一标识,例: "sina"、"netease"
    list_urls: list[str]                     # 入口列表页,按顺序抓

    def parse_list(self, html: str, url: str) -> list[ArticleCandidate]:
        """从列表页 HTML 抽出详情页 URL + 标题 + 频道。
        返回的候选不直接入库,先过 cleaner + dedup。"""

    def parse_detail(self, html: str, url: str) -> Article | None:
        """从详情页抽正文/作者/发布时间/正文类型。
        返回 None 表示「放弃这条」(404 / 维护页 / 视频页无文本等)。"""
```

### 接入新站点的硬性约束

| 约束 | 说明 | 违反后果 |
|---|---|---|
| 频道名必须与 `CHANNELS` 对齐 | 频道是导出维度的 group,不可运行时拼 | 数据无法按频道聚合 |
| 列表页 URL 必须稳定 | 改版前会硬编进 `config.py:CHANNEL_URLS` | 改版时只能 patch 配置文件 |
| `parse_list` 不发起网络请求 | 只解析传入的 HTML | 绕开限速 / 重试 / 编码识别 |
| `parse_detail` 必须处理 None | 任何字段缺失要 fallback 到空串而非 raise | 单条崩整批 |
| 时间字段统一 `Asia/Shanghai` | 在 parser 内完成,不要推到 storage | 时区混乱见 SKILL.md 边界情况表 |

## 2. HttpFetcher 内部状态机

```
   ┌──────────┐
   │  IDLE    │
   └────┬─────┘
        │ fetch(url)
        ▼
   ┌──────────┐  拿到 response
   │ ENCODING │ ──────────────┐
   │ DETECT   │               │ 识别失败
   └────┬─────┘               ▼
        │ OK             ┌──────────┐
        ▼                │ FALLBACK │ → chardet → apparent_encoding
   ┌──────────┐          └────┬─────┘
   │   SEND   │               │ OK
   │ REQUEST  │ ◀─────────────┘
   └────┬─────┘
        │ status code
        ▼
   ┌──────────────────────────┐
   │ classify response        │
   │   2xx  → SUCCESS         │
   │   3xx  → follow (≤3)     │
   │   429  → backoff retry   │
   │   5xx  → backoff retry   │
   │   403  → rotate UA retry │
   │   404  → DEAD (no retry) │
   └──────────────────────────┘
        │
        ▼
   ┌──────────┐
   │ METRICS  │  计入 latency / status / bytes
   └──────────┘
```

### 编码识别优先级(从高到低)

1. HTTP `Content-Type` 头里的 `charset=`
2. `<meta charset="...">` / `<meta http-equiv="Content-Type" content="...;charset=...">`
3. `cchardet` 嗅探(置信度 ≥ 0.7 才采纳)
4. `requests.Response.apparent_encoding` 兜底
5. 最后 fallback `utf-8` + `errors="replace"`(不抛异常,日志 warning)

## 3. 限速器选型矩阵

框架提供两种,选哪个看场景:

| 维度 | TokenBucket | SlidingWindow |
|---|---|---|
| 行为 | 允许短时突发(burst),平均速率受控 | 任何 N 秒窗口内请求数 ≤ K,无突发 |
| 实现 | 单一时间戳 + 容量计数 | 双向队列存时间戳 |
| 内存 | O(1) | O(N),N = 窗口内最大请求数 |
| 适合 | 偶发峰值友好(列表页集中抓) | 严格不超阈(对方反爬极严) |
| 默认场景 | 新闻列表抓取 | 高频实时监控 |
| 配置项 | `RATE_LIMITER=token` | `RATE_LIMITER=sliding` + `WINDOW_SIZE=10` `WINDOW_MAX=5` |

### 抖动(jitter)的重要性

固定间隔 = 周期性峰值,极易被反爬识别为机器人。两种限速器都内置 `±20%` 抖动,`HTTP_MIN_INTERVAL=1.0` 实际执行 0.8-1.2 秒。**不要关掉它**。

## 4. 持久化写入路径

```
ArticleCandidate (parser)
    │
    ▼
cleaner.clean_text()           ← 去广告 / 去责编 / 去来源前缀
    │
    ▼
url_hash = sha1(url)[:16]      ← 16 字符够 2^80,撞库概率可忽略
    │
    ▼
repository.upsert(article)
    │
    ├─ IntegrityError (UNIQUE 冲突)
    │      └─ 转为 UPDATE content / published_at
    │
    └─ OK
           └─ metrics 记 +1 inserted / updated
```

### 批量 upsert 性能来源

- `pymysql` 纯 Python,但**单连接**事务内 batch insert 实测 4447/s
- 关键点:`SQLAlchemy` 的 `session.bulk_save_objects` 绕过 identity map
- 关闭 `echo=True`、关闭 `autoflush`,配合 `chunk_size=500` 批量 commit

## 5. 性能调优清单

按收益从大到小:

1. **调整 `HTTP_TIMEOUT`**:默认 15s,慢站点可调到 20s,但**不要超过 30s** — 单条拖太久会触发上游连接池排队
2. **启用 `USER_AGENT_ROTATE`**:真实 UA 池 30+,降低 403 概率
3. **提高 `MAX_ARTICLES_PER_CHANNEL`**:单进程内批量插入比多次启动更高效
4. **MySQL 连接池**:`SQLALCHEMY_POOL_SIZE=10`、`POOL_RECYCLE=3600` 避免长连接超时
5. **关闭 `echo=True`**:I/O 节省 30%+
6. **DNS 缓存**:`requests` 默认不缓存,在 `utils/` 加 `dnspython` 缓存可省 50-100ms/请求

## 6. 可观测性埋点

`metrics.py` 暴露的指标,按「该看什么」分组:

| 类别 | 指标 | 看什么 |
|---|---|---|
| 吞吐 | `articles_inserted_total` | 抓取产出 |
| 吞吐 | `articles_per_channel{channel=...}` | 频道间是否均匀 |
| 质量 | `parse_errors_total{type=...}` | parser 健壮性 |
| 质量 | `dead_urls_total` | 404 比例(>5% 就要查列表页) |
| 性能 | `fetch_latency_seconds{quantile=...}` | 抓取 P50 / P95 |
| 性能 | `db_write_latency_seconds` | 写入是否成为瓶颈 |
| 限速 | `rate_limit_wait_seconds_total` | 真实花在「等令牌」上的时间 |
| 限速 | `http_status_total{status=...}` | 429/5xx 比例 |

输出位置:`./logs/crawl_stats.json` 每次 crawl 落盘一份,含每频道 breakdown。
