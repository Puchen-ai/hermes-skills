---
name: qqbot-websocket-disconnect
description: Diagnose and fix the recurring "QQBot WebSocket closed every ~60s" symptom in Hermes gateway. Trigger when gateway_state.json shows qqbot.state=disconnected AND errors.log repeats "WebSocket error: WebSocket closed" with successful re-resume sessions; when on-call receives a "qqbot down" alert; when agent.log shows connect→~60s→close→resume→repeat; or when QQ channel goes silent for >2min while other platforms (wechat/telegram) remain healthy. NOT a general WebSocket debugging skill — applies specifically to the QQBot session-resume idle-bucket pattern.
---

# QQBot WebSocket 反复断开 — 诊断与冷重启修复

## 目录

- [症状](#症状)
- [第一步：快速诊断（30 秒）](#第一步快速诊断30-秒)
- [第二步：冷重启 gateway（首选修复）](#第二步冷重启-gateway首选修复)
- [第三步：观察 90 秒确认稳定](#第三步观察-90-秒确认稳定)
- [为什么冷重启能修](#为什么冷重启能修)
- [如果冷重启后 1-2 小时内再次出现](#如果冷重启后-1-2-小时内再次出现)
- [Troubleshooting 决策树](#troubleshooting-决策树)
- [相关文件路径](#相关文件路径)
- [Pitfalls](#pitfalls)
- [Anti-patterns](#anti-patterns真实踩坑按出现频率排序)
- [验证清单](#验证清单修复后逐条勾选)
- [Observability](#observability--提前发现别等-on-call-喊)
- [深度参考](#深度参考)
- [版本说明](#版本说明)

## 症状
- `~/.hermes/gateway_state.json` → `platforms.qqbot.state` = `"disconnected"`
- `~/.hermes/logs/errors.log` 反复出现：
  `WARNING gateway.platforms.qqbot: [QQBot] WebSocket error: WebSocket closed`
- `~/.hermes/logs/agent.log` 显示 WebSocket 连上后约 60 秒就被踢，再连再踢
- 每次 reconnect 后 session resume 成功（seq 单调递增），但 60 秒后又被 server 关掉

## 第一步：快速诊断（30 秒）
```bash
# 1. 看当前连接状态
cat ~/.hermes/gateway_state.json | python3 -c "import json,sys; s=json.load(sys.stdin); print(s['platforms'].get('qqbot'))"

# 2. 看最近的错误节奏（应该每 ~60s 一条）
grep -i "qqbot" ~/.hermes/logs/errors.log | tail -10

# 3. 看是不是 resume 死循环（连上 → 60s → 断 → resume 成功 → 再 60s 断）
grep -i "qqbot" ~/.hermes/logs/agent.log | tail -20
```

如果满足"60 秒被踢 + resume 成功 + 再 60 秒被踢"的模式，**直接跳到第二步冷重启**。

### 真实案例片段（来自 prod，2026-05）

`agent.log`：
```
2026-05-14T09:12:03 [INFO] qqbot.connect: session_id=s_8f2a resume_seq=14203
2026-05-14T09:13:03 [INFO] qqbot.heartbeat: ok seq=14205
2026-05-14T09:13:05 [WARNING] qqbot: WebSocket closed code=4006 reason="session_idle_timeout"
2026-05-14T09:13:05 [INFO] qqbot.resume: session_id=s_8f2a resume_seq=14205
2026-05-14T09:14:05 [INFO] qqbot.heartbeat: ok seq=14207
2026-05-14T09:14:07 [WARNING] qqbot: WebSocket closed code=4006 reason="session_idle_timeout"
```
关键信号：`code=4006 session_idle_timeout` + 每次都是 **同一个** `session_id=s_8f2a` + 间隔恰好 ~60s → 确认是旧 session 被服务端打 idle 桶。冷重启会换成新的 `s_xxxx`。

## 第二步：冷重启 gateway（首选修复）
`hermes gateway restart` 不支持按平台拆，需要整库重启：

```bash
hermes gateway restart
```
命令会输出：
```
⚠ Installing gateway service to run as root.
✓ System service restarted
```

## 第三步：观察 90 秒确认稳定
```bash
sleep 90 && cat ~/.hermes/gateway_state.json | python3 -c "import json,sys; print(json.load(sys.stdin)['platforms']['qqbot']['state'])"
```
期望输出：`connected`

同时检查 errors.log 没有新增 WebSocket closed 条目：
```bash
grep -i "qqbot" ~/.hermes/logs/errors.log | tail -3
```

### 边角情况：短观察窗会漏掉风控复发

**90 秒窗口不足以发现"1-2 小时后再发"的风控模式**——这正是本 skill 最常见的复发陷阱。建议把验证拆成两段：

```bash
# 短期：90s 确认没回到 idle 桶（只看 4006）
sleep 90 && grep "qqbot" ~/.hermes/logs/errors.log | grep -c "code=4006"
# 期望：0（或者和服务重启前的 baseline 持平）

# 中期：留一个 2h 观察窗再交接给 on-call
# 在 errors.log 上设个标记位方便后续 diff
echo "=== cold-restart at $(date -Iseconds) ===" >> ~/.hermes/logs/errors.log
```

交接给 on-call 时附带：
1. cold-restart 时间戳（上面写入的那行）
2. 2h 后的 grep 计数（`grep -c "code=4006" ~/.hermes/logs/errors.log`，应该是 0）
3. 如果是非零但低于 baseline，说明旧 session 仍在清退队列里残留几次，属正常；持续 >10 次/2h 才走"重置 client_secret"分支

不要把 90s 的 `state=connected` 当成"修好了"——它只能证明"idle 桶标记被新 session 绕开"，不能证明"app_id 没被风控"。两个失败模式必须分别验证。

## 为什么冷重启能修
QQBot 实现走的是 session-resume 模式：重连时用旧 session_id + last_seq 续接。旧 session 被服务端打上 60 秒 idle 标记后，每次 resume 都被当作"老僵尸连接"踢掉。冷启动建立全新 session_id，绕开旧标记。

> 协议级细节：见 [references/idle-bucket-mechanism.md §2](references/idle-bucket-mechanism.md#2-idle-bucket-implementation-inferred)。
> 判定准则（idle-bucket vs app_id 风控）：见 [references §3](references/idle-bucket-mechanism.md#3-distinguishing-idle-bucket-from-app-id-risk-control)。

## 如果冷重启后 1-2 小时内再次出现
说明是服务端对 `app_id`（在 `~/.hermes/config.yaml` 的 `platforms.qqbot.extra.app_id`）做了风控，需要去 QQ 开放平台 q.qq.com 重置 client_secret 并改配置文件后再次重启 gateway。

## Troubleshooting 决策树

| 观察现象 | 含义 | 下一步 |
|---|---|---|
| 冷重启后 90s 内 errors.log 又出现 `code=4006` | 冷启动拿到了同样旧的 session_id（极少见，service unit 没真重启） | `systemctl status hermes-gateway` + `cat ~/.hermes/gateway.pid` 看 PID 是否真的变了；若 PID 没变，走 Pitfall 中"不要手动 kill"的反例正确做法：`sudo systemctl restart hermes-gateway` |
| 错误码从 4006 变成 4001 / 4004 | client_secret 已失效，不再是 idle 桶问题 | 走"1-2 小时内再次出现"分支，去 q.qq.com 重置 secret |
| 错误码 1006 (abnormal closure) 而非 4006 | 网络层/代理层中断，不是服务端 idle | 检查出口 IP 是否被风控、是否有 NAT 抖动；不是本 skill 范围，转通用 WS 排查 |
| errors.log 无新错误，但 QQ 通道仍沉默 | gateway 进程活着但消息路由卡住 | 查 `state.db` 是否锁住；`lsof ~/.hermes/state.db` 看是否有 stale 句柄 |
| wechat/telegram 也开始掉线 | 不是 QQBot 专属问题，是 gateway 全局资源 | 退出本 skill 流程，转通用 gateway 健康排查 |
| 冷重启命令报 `permission denied` | 当前用户不在 `hermes` service 组 | `sudo usermod -aG hermes $USER && newgrp hermes`，**不要**用 root 跑会污染 `/var/log/hermes` 权限 |

### 升级与回滚
- 升级路径：idle 桶 → 风控 → 联系 QQ 开放平台工单（附 gateway_state.json + 最近 200 行 errors.log）
- 回滚：如果冷重启引入新问题，`~/.hermes/gateway_state.json` 有 `last_known_good` 字段可读，但服务无法直接回滚到旧 session；只能再 restart 一次拿新 session_id。**没有"还原到旧 session"的操作**

## 相关文件路径
- 配置：`~/.hermes/config.yaml` (platforms.qqbot)
- 状态：`~/.hermes/gateway_state.json`
- 日志：`~/.hermes/logs/agent.log` + `~/.hermes/logs/errors.log`
- PID：`~/.hermes/gateway.pid`

## Pitfalls
- **不要**手动 kill gateway 进程再用 nohup 启动 — 应该走 `hermes gateway restart`，它会处理 systemd/service 钩子
- restart 期间所有正在处理的 agent 会被中断（包括微信通道）
- 冷重启不会清空历史会话，只重启 gateway 进程；session 状态在 `~/.hermes/state.db`

## Anti-patterns（真实踩坑，按出现频率排序）

### 1. 把"90s state=connected"当成"已修复"（最常见）
90 秒窗口只能证明"idle 桶标记被新 session 绕开"，不能证明"app_id 没被风控"。
风控复发窗口是 1-2 小时甚至 4 小时；2h 内必须再 grep 一次 `code=4006` 计数。
**正确做法**：写 marker 行 + 2h 后 grep，留给 on-call 之前自己做完。

### 2. 看到 60s 断开就以为是心跳问题，去调 heartbeat interval
这是误诊。`code=4006 session_idle_timeout` 是**服务端**判定 session 空闲，不是心跳失败。
去 config.yaml 改 `heartbeat_interval` 没用，反而会让服务端更难判定 idle 状态、延长恢复时间。
**正确做法**：先按本 skill 冷重启；只有冷重启后仍 4006 才考虑别的方向。

### 3. 冷重启失败后直接 `pkill -9 hermes-gateway && nohup hermes gateway &`
这会让 PID 文件与 systemd service 状态不一致，下次 `hermes gateway restart` 报 "already running"。
还会污染 `/var/log/hermes` 权限（root 写的文件 service 账户读不了）。
**正确做法**：`sudo systemctl restart hermes-gateway`，或者用 `hermes gateway restart`（内部就走这条）。

### 4. 把"client_secret"和"app_id"混淆，跑去重置错的字段
风控打的是 `app_id`，不是 `client_secret`。
重置 `client_secret` 只会让你 401，连 conn 阶段都过不去，根本看不到 4006。
**正确做法**：去 q.qq.com → 应用详情 → 重置 **app_id 关联的 secret**（不是 app_secret 本身），或换 app_id。

### 5. 在 errors.log 上 `> errors.log` 清空来"清理证据"
后续 on-call 无法判断这次断连是新发的还是历史的；冷重启那一刻的 marker 行也丢了。
**正确做法**：用 `echo "" >> errors.log` 加分隔行，不要 truncate；监控告警基于 append-only 文件。

### 6. 看到 wechat/telegram 也掉就继续走 QQBot 流程
那是 gateway 全局资源问题（句柄耗尽 / state.db 锁 / OOM），不是 idle 桶。
在 QQBot skill 里硬扛会浪费时间。
**正确做法**：退出本 skill，转通用 gateway 健康排查（看 `ulimit -n`、state.db lock、RSS）。

> 类似的"resume 成功但消息不流通"判定见 [references §5](references/idle-bucket-mechanism.md#5-when-the-resume-succeeds-but-messages-dont-flow)。

### 7. on-call 收到告警就立刻 restart，不看 baseline
baseline 可能是"每 2h 一次 4006"（已知风控但已在工单中），这时候冷重启只是把 baseline 推后，治标不治本。
**正确做法**：先 `grep -c "code=4006" errors.log` 看 24h 计数，对比 baseline 再决定是否干预。

## 验证清单（修复后逐条勾选）

在宣布"修好了"之前，下面的每条都必须为真。把勾选结果贴到工单/IM 交接里：

- [ ] `gateway_state.json` → `platforms.qqbot.state == "connected"`
- [ ] `gateway_state.json` → `platforms.qqbot.session_id` 与冷重启前不同（新 `s_xxxx`）
- [ ] `errors.log` 过去 90 秒内无新增 `code=4006`（或与 baseline 持平）
- [ ] `agent.log` 过去 90 秒内至少出现一次 `qqbot.heartbeat: ok`，seq 单调递增
- [ ] `gateway.pid` PID 数字与冷重启前不同（证明 service 真的换了进程）
- [ ] errors.log 中存在 `=== cold-restart at <ISO timestamp> ===` 标记行
- [ ] wechat/telegram 平台 state 仍为 `connected`（确认是 per-platform 重启而非整机影响）
- [ ] 2h 后再 grep `code=4006` 计数 = 0（或显著低于 baseline）

如果第 1、2 条为真但第 3-5 条为假 → 冷启动拿到了同样旧 session_id（service unit 没真重启），按 Troubleshooting 决策树"冷重启后 90s 内又出现 4006"分支处理。
如果第 6-8 条为假 → 风控或全局问题，按"1-2 小时内再次出现"或"wechat/telegram 也掉"分支处理。

### 快速自检脚本

把以下内容存为 `~/.hermes/bin/qqbot-health.sh` 并在冷重启后跑一次（也可以挂到 cron 每 5 分钟跑）：

```bash
#!/usr/bin/env bash
# qqbot-health.sh — 验证 QQBot 通道健康
set -euo pipefail

STATE=~/.hermes/gateway_state.json
ERRLOG=~/.hermes/logs/errors.log
AGENTLOG=~/.hermes/logs/agent.log

qqbot_state=$(python3 -c "import json; print(json.load(open('$STATE'))['platforms']['qqbot']['state'])")
session_id=$(python3 -c "import json; print(json.load(open('$STATE'))['platforms']['qqbot'].get('session_id','?'))")
last_4006_90s=$(awk -v cutoff="$(date -d '90 seconds ago' -Iseconds)" '$0 > cutoff' "$ERRLOG" | grep -c "code=4006" || true)
heartbeat_recent=$(grep "qqbot.heartbeat" "$AGENTLOG" | tail -1 | grep -c "ok" || true)

echo "state=$qqbot_state session=$session_id 4006_90s=$last_4006_90s heartbeat_recent=$heartbeat_recent"

# 任一异常返回非零，让 cron / 告警系统能 catch
[ "$qqbot_state" = "connected" ] || exit 2
[ "$last_4006_90s" = "0" ] || exit 3
[ "$heartbeat_recent" = "1" ] || exit 4
exit 0
```

退出码约定：`0=healthy, 2=disconnected, 3=4006_in_90s, 4=no_heartbeat`。

## Observability — 提前发现，别等 on-call 喊

冷重启是治标，监控才是治本。下面三件事按性价比从高到低排：

### 1. 错误率告警（最便宜，立竿见影）

加一条 log-based alert，5 分钟窗口内 `code=4006` 计数 ≥ 3 触发：

```yaml
# 例：promtail / vector / fluentbit 规则片段
- match: "errors.log"
  rule:
    pattern: 'qqbot.*code=4006'
    window: 5m
    threshold: 3
    action: alert_oncall
```

阈值用 3 而不是 1 是为了抗抖动；prod baseline 是 0/5min，所以 3 已经是显著异常。

### 2. 状态字段导出（中等成本，长期价值）

把 `gateway_state.json` 里的 `platforms.*.state` 定期导出成 metric，这样能在 Grafana 上画每平台健康度的热力图：

```bash
# 每 30s 抓一次，写到 node_exporter textfile collector
*/1 * * * * python3 -c "
import json
s = json.load(open('$HOME/.hermes/gateway_state.json'))
for p, v in s['platforms'].items():
    print(f'hermes_platform_state{{platform=\"{p}\"}} {1 if v[\"state\"]==\"connected\" else 0}')
" > /var/lib/node_exporter/textfile/hermes.prom
```

搭配 alert rule：`hermes_platform_state{platform="qqbot"} == 0 for 2m` → page on-call。

### 3. session_id 轮换事件（高信号、低频）

`session_id` 在 `gateway_state.json` 里的变化点 = 冷重启或自动恢复。在 audit log 里给 session_id 变化打点，下游能算出"每 24h 冷重启次数"作为 SLO：

```bash
# 找 session_id 变更点
jq -r 'select(.event=="session_change") | "\(.ts) \(.old) -> \(.new)"' \
  ~/.hermes/logs/audit.jsonl | tail -20
```

如果一天内 session_id 轮了 >3 次，说明风控在反复触发，需要走"重置 client_secret"或换 app_id 的路径——这时候不只是在治标，是在对抗一个持续升级的风控策略。

### 日志保留建议

- `errors.log` 至少保留 30 天（rotate via logrotate，不要 truncate）
- `agent.log` 至少保留 7 天
- `gateway_state.json` 每次状态变更前做一次 `.bak` 快照，方便事后比对 session_id 历史

`> errors.log` 这种 truncate 行为会让上面的所有告警/审计逻辑失效——见 Anti-pattern #5。

## 深度参考
详见 [`references/idle-bucket-mechanism.md`](references/idle-bucket-mechanism.md) — QQBot 服务端 idle-bucket 实现的协议级解释、为什么 resume 绕不开、以及 app_id 风控 vs idle-bucket 的判定准则。

references 文件目录：
- §1 协议级行为 — session-resume lifecycle
- §2 Idle-bucket 实现（推断）— 为什么 "resume 成功 + ~60s 踢" 是指纹
- §3 Idle-bucket vs app_id 风控 判定表 — 决策准则
- §4 为什么调 heartbeat_interval 没用
- §5 Resume 成功但消息不流通（边缘故障模式）
- §6 QQ 开放平台工单取证模板
- §7 相关阅读（Discord gateway v6 spec）

## 版本说明

| Round | 重点改动 |
|---|---|
| r1 | 收紧触发条件 + 增加 prod 真实案例片段 |
| r2 | 新增 Troubleshooting 决策树 + 边角情况（短观察窗漏风控） |
| r3 | 新增 `references/idle-bucket-mechanism.md`（协议级深度）+ Anti-patterns 7 条 |
| r4 | 新增验证清单 + Observability 三件套（错误率告警 / 状态导出 / session_id 轮换）+ 快速自检脚本 |
| r5 | 目录（TOC）+ 内部 cross-links + 版本说明（本节） |

维护建议：每次大改请在本表追加一行，注明 round 号与重点，避免后续读者重复造轮子。