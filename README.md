# hermes-skills

我在 Hermes 里写的 9 个 skill,按分类整理。

源:`/root/.hermes/skills/`(2026-06-18 同步)

## 列表

| 分类 | Skill | 用途 |
|---|---|---|
| devops | [qqbot-websocket-disconnect](./devops/qqbot-websocket-disconnect/SKILL.md) | 排查 Hermes gateway 里 QQBot WebSocket 每 ~60s 断连的问题 |
| (root) | [shop-spider](./shop-spider/SKILL.md) | 中文电商爬虫框架(京东 / 淘宝 / 美团 / 拼多多),MySQL + 反爬 |
| (root) | [news-spider](./news-spider/SKILL.md) | 中文新闻爬虫框架(新浪 / 网易),Site Adapter 协议 + MySQL |
| (root) | [alinux3-python-env](./alinux3-python-env/SKILL.md) | Alibaba Cloud Linux 3 上 Python 工具链速查 |
| software-development | [chinese-news-scraper](./software-development/chinese-news-scraper/SKILL.md) | 中文新闻爬虫英文版(与 news-spider 互补) |
| (root) | [cron-web-fetch-fallback](./cron-web-fetch-fallback/SKILL.md) | cron 抓网页失败时优雅降级、不编造内容 |
| productivity | [ai-news-daily-cron](./productivity/ai-news-daily-cron/SKILL.md) | 每日 AI 新闻聚合 cron(HN API + 备用策略,产出 WeChat-ready markdown) |
| (root) | [karpathy-guidelines](./karpathy-guidelines/SKILL.md) | Karpathy 的 LLM 编码行为准则(MIT) |
| social-media | [weibo-monitoring](./social-media/weibo-monitoring/SKILL.md) | 微博用户监控(为什么浏览器/curl 行不通) |

## 用法

每个子目录就是一个独立 skill,核心文件 `SKILL.md`(frontmatter + 触发条件 + 步骤)。

参考:[shop-spider/references/quickstart.md](./shop-spider/references/quickstart.md)

## 许可证

`karpathy-guidelines` 来自上游,保留 **MIT License**(详见其 SKILL.md frontmatter)。
其余为本仓库原创。
