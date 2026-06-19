# hermes-skills

我在 [Hermes Agent](https://github.com/NousResearch/hermes-agent) 生态里写的 9 个 skill，按主题分类整理。每个子目录都是一个**独立可移植**的 skill，复制到 `~/.hermes/skills/<name>/` 即可被 Hermes 加载。

> **源**：`/root/.hermes/skills/`（2026-06-18 同步）  
> **维护者**：[Puchen-ai](https://github.com/Puchen-ai)  
> **协议**：除 `karpathy-guidelines` 外均为本仓库原创，详见各 `SKILL.md` frontmatter

---

## 目录

- [项目结构](#项目结构)
- [Skill 总览（9 个）](#skill-总览9-个)
  - [devops](#devops)
  - [productivity](#productivity)
  - [social-media](#social-media)
  - [software-development](#software-development)
  - [alinux3-python-env](#alinux3-python-env)
  - [cron-web-fetch-fallback](#cron-web-fetch-fallback)
  - [karpathy-guidelines](#karpathy-guidelines)
  - [news-spider](#news-spider)
  - [shop-spider](#shop-spider)
- [如何使用](#如何使用)
- [约定与规范](#约定与规范)
- [贡献与同步](#贡献与同步)
- [许可证](#许可证)
- [变更记录](#变更记录)

---

## 项目结构

```
hermes-skills/
├── README.md                       # 本文件
├── devops/                         # 运维 / 故障排查
│   └── qqbot-websocket-disconnect/
├── productivity/                   # 效率工具
│   └── ai-news-daily-cron/
├── social-media/                   # 社交平台相关
│   └── weibo-monitoring/
├── software-development/           # 软件开发辅助
│   └── chinese-news-scraper/
├── alinux3-python-env/             # 环境速查（root）
├── cron-web-fetch-fallback/        # cron 抓网页降级（root）
├── karpathy-guidelines/            # LLM 编码准则（root）
├── news-spider/                    # 中文新闻爬虫框架（root）
└── shop-spider/                    # 中文电商爬虫框架（root）
```

每个 skill 目录的内部约定：

```
<skill-name>/
├── SKILL.md              # frontmatter + 触发条件 + 步骤（必需）
├── references/           # 速查表、API 文档、协议说明
├── scripts/              # 可执行的辅助脚本（可选）
└── examples/             # 真实使用案例（可选）
```

---

## Skill 总览（9 个）

按目录分组，每个 skill 给出**触发场景 + 关键能力**。

### devops

#### [`qqbot-websocket-disconnect`](./devops/qqbot-websocket-disconnect/SKILL.md)

- **用途**：排查 Hermes gateway 里 QQBot WebSocket 每 ~60s 断连的问题
- **触发信号**：
  - `gateway_state.json` 显示 `qqbot.state=disconnected`
  - `errors.log` 反复出现 `WebSocket error: WebSocket closed` 但 resume 成功
  - on-call 收到 "qqbot down" 告警
  - agent.log 出现 `connect → ~60s → close → resume → repeat` 模式
  - QQ 频道静默 >2min 而微信/Telegram 正常
- **关键能力**：定位是 session-resume idle-bucket 模式导致，给出最小修复
- **不适用**：通用 WebSocket 调试 —— 只针对 QQBot + Hermes 组合

### productivity

#### [`ai-news-daily-cron`](./productivity/ai-news-daily-cron/SKILL.md)

- **用途**：每日 AI 新闻聚合 cron
- **触发信号**：用户要"每天给我 AI 新闻"、"早报"、"AI 资讯推送"
- **关键能力**：
  - 主源：Hacker News Algolia API（网络受限时也可用）
  - 多源降级 + 备用策略矩阵
  - 产出**微信可发布**的 markdown（emoji/链接/排版已优化）
  - 按参与度排序、去重、生成摘要
- **典型场景**：早上 7:00 跑一次 → 生成当天早报 → 自动推送到微信

### social-media

#### [`weibo-monitoring`](./social-media/weibo-monitoring/SKILL.md) `v1.4.5`

- **用途**：监控微博用户动态、timeline、搜索结果
- **触发信号**：要监控某个 V 发博、关键词追踪、舆情采集
- **关键能力**：
  - 解释**为什么浏览器/curl 走不通**（m站的反爬、H5 加密、cookie 滑动）
  - 给出替代方案：微博 Open API + OAuth2
  - 速率限制与签名规则速查
- **不适用**：需要实时秒级推送的场景（API 有频率限制）

### software-development

#### [`chinese-news-scraper`](./software-development/chinese-news-scraper/SKILL.md)

- **用途**：构建中文新闻站点的 Python 爬虫
- **支持站点**：新浪 / 网易 / 腾讯 / 搜狐 / 凤凰
- **触发信号**：用户提到"爬新浪/网易/腾讯新闻"、"中文新闻聚合"、"中文爬虫"
- **关键能力**：
  - GBK 编码处理、UA 轮换、限速
  - SQLite / PostgreSQL 存储适配
  - 礼貌爬取（robots.txt、间隔、退避）
- **不适用**：纯英文站点、需要 JS 渲染或过 CAPTCHA 的站点

### alinux3-python-env

#### [`alinux3-python-env`](./alinux3-python-env/SKILL.md)

- **用途**：Alibaba Cloud Linux 3 上 Python 工具链速查
- **触发信号**：在阿里云 ECS / 容器上装 Python、装 pip、装科学计算包
- **关键能力**：
  - 决策树：系统 Python vs pyenv vs conda vs uv
  - time-bomb 风险清单（glibc、openssl、sqlite 版本不匹配）
  - 各发行版的最佳实践 + 已知坑
- **典型场景**：新机器初始化、CI runner 准备、Docker 镜像瘦身

### cron-web-fetch-fallback

#### [`cron-web-fetch-fallback`](./cron-web-fetch-fallback/SKILL.md)

- **用途**：cron 抓网页失败时优雅降级
- **触发信号**：cron 任务要拉取实时网页/新闻，但环境网络受限
- **关键能力**：
  - 快速诊断：sandbox / proxy / DNS / TLS 哪一层挂了
  - tirith 风格的"该不该执行"判断
  - 缓存格式约定（不编造内容、写明跳过原因）
- **核心原则**：**抓不到就明说抓不到，绝不编造内容**

### karpathy-guidelines

#### [`karpathy-guidelines`](./karpathy-guidelines/SKILL.md)

- **用途**：Karpathy 的 LLM 编码行为准则
- **触发信号**："scope creep"、"切线重构"、"别过度设计"、"junior-engineer test"
- **关键能力**：
  - 不复杂化、外科手术式改动
  - 暴露假设、定义可验证的成功标准
  - 反模式矩阵
  - 速查（Quick Reference）+ TOC
- **来源**：上游 MIT License，保留原作者声明

### news-spider

#### [`news-spider`](./news-spider/SKILL.md)

- **用途**：中文新闻爬虫**框架**
- **支持站点**：新浪 / 网易
- **与 `chinese-news-scraper` 的关系**：本 skill 是**框架级**（Site Adapter 协议 + MySQL 存储），后者是**站点级速查**
- **关键能力**：
  - Site Adapter 协议（统一接口、便于扩站点）
  - 反爬矩阵（UA / proxy / 频率 / 验证码识别边界）
  - MySQL 持久化 + 增量更新
  - 架构参考图

### shop-spider

#### [`shop-spider`](./shop-spider/SKILL.md)

- **用途**：中文电商爬虫**框架**
- **支持站点**：京东 / 淘宝 / 美团 / 拼多多
- **触发信号**：做价格监控、商品聚合、SKU 抓取、店铺分析
- **关键能力**：
  - 5 维分类法（商品/订单/评论/店铺/搜索）
  - 适配器扩展机制
  - MySQL + 反爬矩阵
  - 版本演进历史

---

## 如何使用

### 单个 skill 装到 Hermes

```bash
# 1. 选你要的 skill
SKILL=qqbot-websocket-disconnect

# 2. 拷贝到 Hermes 加载目录
cp -r devops/$SKILL ~/.hermes/skills/

# 3. 验证 frontmatter
head -20 ~/.hermes/skills/$SKILL/SKILL.md
```

### 整批装（推荐用 rsync 增量同步）

```bash
rsync -av --delete \
  --exclude='.git' \
  --exclude='README.md' \
  ./ \
  ~/.hermes/skills/
```

> ⚠️ `--delete` 会清掉 `~/.hermes/skills/` 里本仓库没有的内容，**确认没有未纳入仓库的本地 skill 后再跑**。

### 在 Claude Code 里调用

skill 装好后，Hermes 会自动在合适的场景触发。也可用命令显式唤起：

```
@qqbot-websocket-disconnect 今天 qqbot 又断了，帮我看看
@ai-news-daily-cron 给我生成今天的早报
@karpathy-guidelines 帮我 review 一下这个 PR
```

---

## 约定与规范

- **触发信号**：每个 SKILL.md 的 description 必须给出可被 Hermes 匹配的**具体信号**（错误信息、关键词、文件路径），不能写空泛的"用于爬虫"。
- **不适用场景**：明确写出"NOT for X"，避免误触发。
- **不编造**：抓不到的数据写明"未获取" + 原因，不补、不编、不推。
- **路径**：路径写相对仓库根（`./devops/...`），不写绝对路径。

---

## 贡献与同步

- **同步源**：`/root/.hermes/skills/`
- **同步策略**：本地 skill 写好、验证可用后，`cp -r` 进本仓库对应目录，commit + push
- **commit message 规范**：`<type>(<skill>): <5-round 改进点简述>`
  - 例：`feat(weibo-monitoring): 5-round improvement — skeleton to full manual`
- **不接受**：未在 Hermes 实际验证过的 skill PR

---

## 许可证

- `karpathy-guidelines/` —— **MIT License**，源自 [Karpathy LLM Coding Guidelines](https://gist.github.com/karpathy/...)（详见其 SKILL.md frontmatter）
- 其余 8 个 skill —— 本仓库原创，授权方式见各 `SKILL.md` frontmatter

---

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-19 | 9 个 skill 全部经过 5 轮迭代：增加 TOC、决策树、Quick Reference、架构图、anti-pattern 矩阵 |
| 2026-06-18 | 初版 9 个 skill 整理归档 |
