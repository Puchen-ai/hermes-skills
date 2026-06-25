---
name: agent-harness-design
description: |
  造 coding agent / 多 agent 系统的设计模式速查。20 个 harness 机制 + 15 条原则 + 5 段可复用代码,
  来源 shareAI-lab/learn-claude-code (20 章 2000+ 行教学代码, MIT)。
  Trigger: "造 agent" / "做 coding agent" / "agent harness" / "LLM agent 框架" / "subagent 设计" /
           "agent 任务系统" / "上下文压缩" / "MCP 集成" / "多 agent 协作" / "agent 团队" / "agent loop"。
  Skip: 简单 prompt 工程、单轮对话产品、纯 LLM 调用封装。
---

# Agent Harness Design — 30 分钟掌握 20 个核心机制

> 来源: [shareAI-lab/learn-claude-code](https://github.com/shareAI-lab/learn-claude-code) (MIT)
> 学完日期: 2026-06-25 (经 10 轮反复学习,含 s20 综合章 2123 行精读 + 实测验证)
> 姊妹项目: [Kode-cli](https://github.com/shareAI-lab/Kode-cli) (产品), [claw0](https://github.com/shareAI-lab/claw0) (主动常驻), [Kode-agent-sdk](https://github.com/shareAI-lab/Kode-agent-sdk) (嵌入式)

## 0. 一句话核心理念

**Agency 来自模型 (训练得到), Harness 让 agency 落地 (你写的)。**
别用工作流图 / 决策树 / 节点编排模拟智能 — 那是 GOFAI 还魂, 不会涌现自主行为。

## 1. 最小循环 (所有机制的地基, 必背)

```python
def agent_loop(messages, tools, handlers, call_llm):
    while True:
        response = call_llm(messages, tools)            # 1. 调 LLM
        messages.append(as_message(response))            # 2. 追加 assistant
        if not has_tool_use(response):                   # 3. 事实胜于 stop_reason
            return                                       #    看 content 里有没有 tool_use
        results = []                                     # 4. 执行工具
        for block in tool_use_blocks(response):
            if (blocked := trigger_hooks("PreToolUse", block)):
                out = blocked                             #    hook 可拦截
            else:
                out = handlers[block.name](**block.input)
            trigger_hooks("PostToolUse", block, out)
            results.append(tool_result(block, out))
        messages.append(as_user(results))                 # 5. 喂回去
```

**20 个机制都挂在这 5 步上, 循环本身不变。**

## 2. 20 个机制速查表 (按依赖排序)

| 阶段 | ID | 机制 | 关键实现 | 何时需要 |
|------|------|------|---------|---------|
| **基础 (s01-s05)** | s01 | Agent Loop | `while + has_tool_use` | 任何 agent |
| | s02 | Tool Use | `TOOL_HANDLERS[block.name]` dispatch | 多工具 |
| | s03 | Permission | 拒绝列表 → 规则 → 询问 三道闸门 | 写文件 / 删文件 / 跑命令 |
| | s04 | Hooks | `register_hook` + `trigger_hooks` | 想加功能不想改循环 |
| | s05 | TodoWrite | `TodoItem` + 3 轮 reminder | 5 步以上任务 |
| **中级 (s06-s11)** | s06 | Subagent | 独立 `messages[]` + 工具受限 | 调研 / 试错 / 重活 |
| | s07 | Skill Loading | 启动扫目录注入 SYSTEM + 按需 `load_skill` | 领域专长 |
| | s08 | Context Compact | L0 budget + L1 snip + L2 micro + L3 LLM摘要 | 长会话 / 大项目 |
| | s09 | Memory | `.md` 文件 + `MEMORY.md` 索引 + 4 类型 | 跨会话偏好 |
| | s10 | System Prompt | sections 字典 + 运行时组装 | 多项目 / 多工具 |
| | s11 | Error Recovery | `RecoveryState` 类 + `with_retry` 包裹 LLM | 任何生产 agent |
| **高级 (s12-s19)** | s12 | Task System | `.tasks/{id}.json` + `blockedBy` DAG | 多目标协同 |
| | s13 | Background Tasks | daemon thread + `run_in_background` flag | 慢操作 (`pip install` / `npm build`) |
| | s14 | Cron Scheduler | 独立线程 + 队列 + 5 段 cron 表达式 | 周期任务 |
| | s15 | Agent Teams | 文件收件箱 `.jsonl` + 队友线程 | 多模块并行 |
| | s16 | Team Protocols | `request_id` + 状态机 + 门控 | 协商 / 关机 / 计划审批 |
| | s17 | Autonomous Agents | idle_poll 5s + scan_unclaimed | 自治团队 |
| | s18 | Worktree Isolation | `git worktree` + `task.worktree` 字段 | 并行队友不互相覆盖 |
| | s19 | MCP Plugin | MCPClient + `assemble_tool_pool` | 接外部服务 |
| **整合** | s20 | Comprehensive | 19 机制归一循环 | 完整产品 |

## 3. 4 层压缩管线 (s08 + s20 整合, 必装)

**便宜先跑, 贵的后跑, 关键约束: 不拆 `assistant(tool_use)` 和 `user(tool_result)`**

```python
def prepare_context(messages):
    # L0 (s20 新增): 超大 tool_result 持久化到文件, 上下文只留路径+预览
    messages[:] = tool_result_budget(messages, max_bytes=200_000)
    # L1: 裁掉中间旧消息(保留 head 3 + tail 47)
    messages[:] = snip_compact(messages, max_messages=50)
    # L2: 旧 tool_result 占位(只留最近 3 个完整内容)
    messages[:] = micro_compact(messages, keep=3)
    # L3 (贵, 1 API): LLM 摘要
    if estimate_size(messages) > CONTEXT_LIMIT:
        write_transcript(messages)  # 先存 .transcripts/ 留底
        messages[:] = compact_history(messages)  # 再摘要替换
    return messages
```

## 4. 错误恢复的真正做法 (s11 + s20 整合, 必装)

**抽 `RecoveryState` 类 + `with_retry` 函数, 包裹 LLM 调用, 不写进循环**

```python
class RecoveryState:
    has_escalated: bool = False           # max_tokens 8K→64K 升级过没
    recovery_count: int = 0              # 续写次数
    consecutive_529: int = 0              # 连续 529 计数
    has_attempted_reactive_compact: bool = False  # 上下文超限压缩过没
    current_model: str = PRIMARY_MODEL   # fallback model 切换

def with_retry(fn, state):
    for attempt in range(MAX_RETRIES):
        try:
            r = fn()
            state.consecutive_529 = 0
            return r
        except RateLimit: time.sleep(retry_delay(attempt)); continue
        except Overloaded:
            state.consecutive_529 += 1
            if state.consecutive_529 >= 2 and FALLBACK_MODEL:  # 切模型
                state.current_model = FALLBACK_MODEL
            time.sleep(retry_delay(attempt)); continue
        except PromptTooLong:
            if not state.has_attempted_reactive_compact:
                messages[:] = reactive_compact(messages)  # 激进的 L3
                state.has_attempted_reactive_compact = True
                continue  # retry with new context
            raise
    raise RuntimeError("Max retries exceeded")
```

## 5. 多 agent 协议 (s15 + s16 + s20 整合, 进阶)

**三件套: 文件收件箱 + 状态机 + 时间门控**

```python
# 收件箱 (跨线程可观察, 消费式)
class MessageBus:
    def send(self, fr, to, content, type_="message", metadata=None):
        with open(MAILBOX/f"{to}.jsonl", "a") as f:
            f.write(json.dumps({"from":fr,"to":to,"content":content,
                               "type":type_,"metadata":metadata or {},
                               "ts":time.time()})+"\n")
    def read(self, agent):
        f = MAILBOX/f"{agent}.jsonl"
        if not f.exists(): return []
        msgs = [json.loads(l) for l in f.read_text().splitlines() if l]
        f.unlink()  # 消费式
        return msgs

# 状态机
@dataclass
class ProtocolState:
    request_id: str; type: str        # "shutdown" | "plan_approval"
    sender: str; target: str
    status: str                       # pending | approved | rejected
    payload: str; created_at: float

# 时间门控 (s20 独有, s16 没的)
protocol_ctx = {"waiting_plan": None}  # 等待审批期间 model 不能继续
# 在循环里: if protocol_ctx["waiting_plan"]: sleep 5; continue
# submit_plan 后续 tool_use 一律 break(忽略)
```

## 6. 必装组合 (按需求场景)

| 需求 | 必装 |
|------|------|
| 最小 demo | s01 + s02 |
| 日常 coding agent | + s03 + s05 |
| 长任务 (代码重构) | + s04 + s08 + s09 |
| 长期运行 (CI 助手) | + s11 + s12 + s14 |
| 慢操作多 (跑构建) | + s13 |
| 多人协作 (大项目) | + s15 + s16 + s18 |
| 自治团队 | + s17 |
| 接外部 (Jira/Notion) | + s19 |
| 完整产品 | 全部 (s20) |

## 7. 15 条核心原则 (必读)

1. **Agency 来自模型** — 不要再写工作流模拟智能
2. **循环是稳定核心** — 加机制不改循环, 挂 hook
3. **dispatch map 而非 if-else** — `TOOL_HANDLERS[block.name](**block.input)`
4. **权限必须代码化** — 三道闸门(硬拒绝 / 规则 / 询问)
5. **Hooks 是扩展点** — `register_hook` + `trigger_hooks`, 非 None 返回值 = 拦截
6. **压缩分 4 层** — 便宜先跑, 关键约束不拆 tool_use + tool_result
7. **记忆 vs 压缩** — 记忆是文件 (.md), 压缩是临时裁剪
8. **Prompt 是组装** — sections 字典 + 缓存 (命中 prompt cache 省 90% token)
9. **TodoWrite 防漂移** — 5 步以上任务必装, 3 轮 reminder
10. **子 agent = 干净上下文** — 只回传最后一条 assistant text
11. **后台任务不阻塞** — 显式 `run_in_background` 优先, 关键词兜底
12. **任务系统 = DAG** — `blockedBy` 依赖图, 与 TodoWrite 区分
13. **多 agent = 邮箱 + 状态机** — 不要 RPC, 用文件收件箱
14. **自治 = idle 轮询** — 5s 间隔, 60s timeout
15. **并行 = worktree** — 任务管"做什么", worktree 管"在哪做"

## 8. 实施顺序 (第一次做 agent)

1. **抄 s01** 的 20 行循环 (或上面的代码块)
2. **加 s02** `TOOL_HANDLERS` 字典 (bash / read / write / edit / glob)
3. **加 s03** 三道闸门 (在 `handlers[block.name]` 之前)
4. **加 s04** HOOKS (4 事件: PreToolUse / PostToolUse / UserPromptSubmit / Stop)
5. **加 s05** `todo_write` 工具 + 3 轮 reminder
6. **加 s08** compact (L1 + L2 先, L3 后加)
7. **加 s11** error recovery 包裹 LLM (`with_retry` + `RecoveryState`)
8. **按需加** s06 / s07 / s09 / s10 / s12 / s13

**铁律**: 扩展行为时挂 hook, 永远不要改 `agent_loop`。

## 9. 验证 & 调试技巧

```python
# 1. 写一个 mock LLM, 不依赖 API key 也能跑通循环
class MockResp:
    def __init__(self, content, stop_reason="end_turn"):
        self.content = content; self.stop_reason = stop_reason

# 2. 把 agent_loop 拆出来单独测试
# 3. 用 log_hook 打印每次工具调用
# 4. 看 .transcripts/ 找压缩前的现场
# 5. 看 .tasks/ 看任务图状态
# 6. 看 .mailboxes/ 看队友通信
# 7. 看 .worktrees/ 看工作树状态
```

## 10. 完整示例 (s01 + s02 + s04, 不依赖 API key)

```python
"""
Hello World Agent - 教学示例, 跑通最小可用 harness
实测可用: 创建 hello.py → 写 hello 函数 → 跑 → 输出 'Hello, World!'
"""
import os, subprocess, json
from pathlib import Path

WORKDIR = Path.cwd()

# 5 个工具
TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "write_file", "description": "Write a file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
]

def safe_path(p):
    path = (WORKDIR / p).resolve()
    try: path.relative_to(WORKDIR)
    except ValueError: raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command):
    if any(d in command for d in ["rm -rf /", "sudo"]): return "BLOCKED"
    r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10, cwd=WORKDIR)
    return (r.stdout + r.stderr).strip() or "(no output)"

def run_write(path, content):
    fp = safe_path(path); fp.parent.mkdir(parents=True, exist_ok=True); fp.write_text(content)
    return f"Wrote {len(content)} bytes"

# Dispatch map (s02 核心)
TOOL_HANDLERS = {"bash": lambda command: run_bash(command),
                 "write_file": lambda path, content: run_write(path, content)}

# Hooks (s04)
HOOKS = {"PreToolUse": [], "PostToolUse": [], "Stop": []}
def register_hook(event, fn): HOOKS[event].append(fn)
def trigger_hooks(event, *args):
    for fn in HOOKS[event]:
        r = fn(*args)
        if r is not None: return r
    return None

register_hook("PreToolUse", lambda b: print(f"  → {b['name']}"))

# 关键: has_tool_use 替代 stop_reason
def has_tool_use(content): return any(getattr(b, "type", None) == "tool_use" for b in content)

def agent_loop(messages, call_llm):
    while True:
        response = call_llm(messages)
        messages.append({"role": "assistant", "content": [
            {"type": b.type, "name": getattr(b, "name", None), "input": getattr(b, "input", {}), "text": getattr(b, "text", "")}
            for b in response.content
        ]})
        if not has_tool_use(response.content):
            trigger_hooks("Stop", messages); return
        results = []
        for block in response.content:
            if getattr(block, "type", None) != "tool_use": continue
            block_dict = {"name": block.name, "input": block.input}
            blocked = trigger_hooks("PreToolUse", block_dict)
            out = str(blocked) if blocked else TOOL_HANDLERS[block.name](**block.input)
            trigger_hooks("PostToolUse", block_dict, out)
            results.append({"type": "tool_result", "tool_use_id": f"id_{block.name}", "content": out})
        messages.append({"role": "user", "content": results})
```

## 参考资源

| 资源 | 链接 |
|------|------|
| 原始仓库 | https://github.com/shareAI-lab/learn-claude-code |
| s20 综合章 (2123 行) | `/root/study/learn-claude-code/s20_comprehensive/code.py` |
| 完整笔记 (HARNESS-PATTERNS) | `references/HARNESS-PATTERNS.md` |
| 15 条精华 (KEY-INSIGHTS) | `references/KEY-INSIGHTS.md` |
| 20 条反模式 | `references/ANTIPATTERNS.md` |
| 完整 Hello World 示例 | `references/hello_world_agent.py` |
| 姊妹教程 (主动常驻) | https://github.com/shareAI-lab/claw0 |
| 实际产品 (CLI) | https://github.com/shareAI-lab/Kode-cli |
| 嵌入式 SDK | https://github.com/shareAI-lab/Kode-agent-sdk |
