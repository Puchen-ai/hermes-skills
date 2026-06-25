---
name: agent-harness-design
description: |
  造 coding agent / 多 agent 系统时必读。包含从 shareAI-lab/learn-claude-code (20 章, MIT) 提炼的 20 个 harness 机制、15 条精华、可复用代码模板, 适合 coding agent / Claude Code 类产品 / AI 工具编排。
  Trigger: "造 agent" / "做 coding agent" / "agent harness" / "LLM agent 框架" / "subagent 设计" / "agent 任务系统" / "上下文压缩" / "MCP 集成" / "多 agent 协作" / "agent 团队".
  Skip: 简单 prompt 工程、单轮对话产品、纯 LLM 调用封装。
---

# Agent Harness Design — 20 机制速查

> 来源: shareAI-lab/learn-claude-code (20 章 2000+ 行教学代码, MIT)
> 学完日期: 2026-06-25
> 完整笔记: 见 `references/HARNESS-PATTERNS.md` (18KB) + `references/KEY-INSIGHTS.md` (7KB)
> 原始仓库: https://github.com/shareAI-lab/learn-claude-code

## 核心理念（每次都要先讲）

**Agency 来自模型, Harness 让 agency 落地。**
- 智能 → 模型训练得到, 不可写出来
- Harness → 你写的: 循环 + 工具 + 上下文 + 边界
- 不要做: 工作流图 / 决策树 / 节点编排 (那是 GOFAI 还魂)

## 最小循环（所有机制的地基）

```python
def agent_loop(messages, system, tools, handlers):
    while True:
        resp = call_llm(messages, system, tools)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use": return
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = handlers[block.name](**block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        messages.append({"role": "user", "content": results})
```

**所有 19 个机制都挂在这个 while 上, 循环本身不变。**

## 20 个机制速查

| ID | 机制 | 关键代码 | 适用 |
|----|------|---------|------|
| s01 | Agent Loop | `while stop_reason=="tool_use"` | 任何 agent |
| s02 | Tool Use | `TOOL_HANDLERS[block.name]` dispatch | 多工具 |
| s03 | Permission | 拒绝列表 → 规则 → 询问 | 危险操作 |
| s04 | Hooks | `register_hook` + `trigger_hooks` 字典 | 扩展点 |
| s05 | TodoWrite | `TodoItem{status}` + 3 轮 reminder | 长任务 |
| s06 | Subagent | 独立 `messages[]` + 工具受限 | 拆大任务 |
| s07 | Skill Loading | 目录常驻 + 内容按需 tool_result 注入 | 领域知识 |
| s08 | Context Compact | snip/micro/budget/auto 4 层 | 长会话 |
| s09 | Memory | `.md` 文件 + `MEMORY.md` 索引 + 4 类 | 跨会话 |
| s10 | System Prompt | sections 字典 + 缓存复用 | 多项目 |
| s11 | Error Recovery | max_tokens 升级 + 退避 + reactive compact | 任何生产 |
| s12 | Task System | `.tasks/{id}.json` + `blockedBy` DAG | 多目标 |
| s13 | Background Tasks | daemon thread + `run_in_background` | 慢操作 |
| s14 | Cron Scheduler | 独立线程每秒轮询 + 队列 | 周期任务 |
| s15 | Agent Teams | 文件收件箱 `.jsonl` + 队友线程 | 多模块 |
| s16 | Team Protocols | `request_id` + 状态机 | 协商/握手 |
| s17 | Autonomous Agents | idle_poll 5s + scan_unclaimed | 自治团队 |
| s18 | Worktree Isolation | `git worktree` + `task.worktree` 字段 | 并行队友 |
| s19 | MCP Plugin | MCPClient + `assemble_tool_pool` | 接外部 |
| s20 | Comprehensive | 19 机制归一循环 | 完整产品 |

## 15 条核心原则（详见 references/KEY-INSIGHTS.md）

1. **Agency 来自模型** — 不要再写工作流模拟智能
2. **循环是稳定核心** — 加机制不改循环
3. **dispatch map** 而非 if-else
4. **权限必须代码化** — 三道闸门(拒绝/规则/询问)
5. **Hooks 是扩展点** — 不写进循环, 挂在外
6. **压缩分 4 层** — 便宜先跑, 关键约束: 不拆 `tool_use` + `tool_result`
7. **记忆 vs 压缩** — 记忆是文件, 压缩是临时裁剪
8. **Prompt 是组装** — section 字典 + 缓存
9. **TodoWrite 防漂移** — 5 步以上任务必装
10. **子 agent = 干净上下文** — 只回传结论
11. **后台任务不阻塞** — 显式 `run_in_background` 优先
12. **任务系统 = DAG** — 与 TodoWrite 区分
13. **多 agent = 邮箱 + 状态机** — 不要 RPC
14. **自治 = idle 轮询** — 5s 间隔
15. **并行 = worktree** — 任务管目标, worktree 管目录

## 必装组合

| 需求 | 必装 |
|------|------|
| 最小 demo | s01 + s02 |
| 日常 coding | + s03 + s05 |
| 长任务 | + s04 + s08 + s09 |
| 长期运行 | + s12 + s14 |
| 慢操作多 | + s13 |
| 多人协作 | + s15 + s16 + s18 |
| 自治团队 | + s17 |
| 接外部 | + s19 |
| 完整产品 | 全部 (s20) |

## 实施顺序

1. 抄 s01 的 20 行循环
2. 加 s02 TOOL_HANDLERS 字典
3. 加 s03 三道闸门
4. 加 s04 HOOKS (4 事件)
5. 加 s05 todo_write + reminder
6. 加 s08 compact (L1+L2 先)
7. 加 s11 error recovery 包裹 LLM
8. 按需 s06/s07/s09/s10/s12/s13

**铁律: 扩展行为时挂 hook, 永远不要改 agent_loop。**

## 关键代码片段（完整版见 references/HARNESS-PATTERNS.md）

### Dispatch map (s02)
```python
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, ...}
out = TOOL_HANDLERS[block.name](**block.input)
```

### Hooks (s04)
```python
HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}
def register_hook(event, fn): HOOKS[event].append(fn)
def trigger_hooks(event, *args):
    for fn in HOOKS[event]:
        r = fn(*args)
        if r is not None and event in ("PreToolUse", "Stop"): return r
```

### 4 层压缩 (s08)
```python
def compact(messages):
    messages = snip_compact(messages, max=50)
    messages = micro_compact(messages, keep=3)
    if estimate_tokens(messages) > BUDGET: messages = budget_compact(messages)
    if estimate_tokens(messages) > BUDGET: messages = auto_compact(messages)  # LLM 摘要
    return messages
# 关键: 不拆 assistant(tool_use) 和 user(tool_result)
```

### Task DAG (s12)
```python
@dataclass
class Task:
    id: str; subject: str; status: str
    owner: str | None; blockedBy: list[str]; worktree: str | None
def can_start(t): return t.owner is None and all(load_task(d).status=="completed" for d in t.blockedBy)
```

### MessageBus (s15)
```python
class MessageBus:
    def send(self, fr, to, content, type_="message"):
        with open(MAILBOX/f"{to}.jsonl", "a") as f:
            f.write(json.dumps({"from":fr,"to":to,"content":content,"type":type_,"ts":time.time()})+"\n")
    def read(self, agent):
        f = MAILBOX/f"{agent}.jsonl"
        if not f.exists(): return []
        msgs = [json.loads(l) for l in f.read_text().splitlines() if l]
        f.unlink()  # 消费式
        return msgs
```

## 参考资源

- 完整笔记: `references/HARNESS-PATTERNS.md` (20 机制 + 代码模板)
- 15 条精华: `references/KEY-INSIGHTS.md` (设计原则)
- 原始仓库: https://github.com/shareAI-lab/learn-claude-code
- s20 code.py: https://github.com/shareAI-lab/learn-claude-code/blob/main/s20_comprehensive/code.py (2123 行, 完整 harness 实现)
- 姊妹教程 claw0: https://github.com/shareAI-lab/claw0 (主动式常驻 agent)
