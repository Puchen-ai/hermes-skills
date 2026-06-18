---
name: qqbot-websocket-disconnect
description: Diagnose and fix the recurring "QQBot WebSocket closed every ~60s" symptom in Hermes gateway. Applies when gateway_state.json shows qqbot.state=disconnected and errors.log repeats "WebSocket error: WebSocket closed" with successful re-resume sessions.
---

# QQBot WebSocket 反复断开 — 诊断与冷重启修复

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

## 为什么冷重启能修
QQBot 实现走的是 session-resume 模式：重连时用旧 session_id + last_seq 续接。旧 session 被服务端打上 60 秒 idle 标记后，每次 resume 都被当作"老僵尸连接"踢掉。冷启动建立全新 session_id，绕开旧标记。

## 如果冷重启后 1-2 小时内再次出现
说明是服务端对 `app_id`（在 `~/.hermes/config.yaml` 的 `platforms.qqbot.extra.app_id`）做了风控，需要去 QQ 开放平台 q.qq.com 重置 client_secret 并改配置文件后再次重启 gateway。

## 相关文件路径
- 配置：`~/.hermes/config.yaml` (platforms.qqbot)
- 状态：`~/.hermes/gateway_state.json`
- 日志：`~/.hermes/logs/agent.log` + `~/.hermes/logs/errors.log`
- PID：`~/.hermes/gateway.pid`

## Pitfalls
- **不要**手动 kill gateway 进程再用 nohup 启动 — 应该走 `hermes gateway restart`，它会处理 systemd/service 钩子
- restart 期间所有正在处理的 agent 会被中断（包括微信通道）
- 冷重启不会清空历史会话，只重启 gateway 进程；session 状态在 `~/.hermes/state.db`