# Key Insights — 自己造 agent harness 必须记住的 15 条

> 来自对 learn-claude-code 20 章 + 2000+ 行 code 的精读

---

## 1. Agency 来自模型，不是来自代码

**最根本的一点：所有"智能"都在模型里。Harness 只是给模型一个可工作的环境。**
不要再用 if-else / 工作流图 / 节点编辑器去模拟智能——那是 GOFAI 还魂。
LLaMA/Claude/Qwen 这些模型已经学会了"在什么情况下调用什么工具"，你的工作只是给它：
- 工具（read/write/bash/...）
- 上下文（文件内容、记忆、错误）
- 边界（权限、审批）
- 循环（让模型能多轮调用工具直到完成）

## 2. 循环是稳定核心，机制是装饰

```
def agent_loop(messages):
    while True:
        resp = LLM(messages, tools)
        if resp.stop_reason != "tool_use": return
        execute_tools(resp)
        append_results(messages)
```

**所有 19 个机制都挂在这个 while 上。** 循环本身从不改。加新功能 = 在循环周围加东西，不是改循环。

## 3. "加工具"是加一行代码，不是加一个 if

```python
# 错的写法
if tool_name == "bash": run_bash(...)
elif tool_name == "read_file": run_read(...)
elif tool_name == "edit_file": run_edit(...)
# 100 个工具 = 100 个 elif

# 对的写法
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, ...}
out = TOOL_HANDLERS[block.name](**block.input)
```

`dispatch map` 是 agent harness 最基础的扩展模式。

## 4. 权限必须代码化，不能靠信任模型

模型说"我不会 rm -rf"≠ 它不会 rm -rf。
**硬拒绝列表（字符串模式）+ 规则匹配（路径/操作类型）+ 用户审批（异步）**——三道闸门顺序固定。
最危险的操作必须 hard-code 拒绝，无论模型怎么说"我确认"。

## 5. Hooks 是扩展点的设计模式

当你想"在 X 之前/之后做 Y"时，**不要改循环**。
加一个事件名（`PreToolUse` / `PostToolUse` / `UserPromptSubmit` / `Stop`），加一个注册函数。
循环只调用 `trigger_hooks(event, *args)`，具体跑什么由注册表决定。

**非 None 返回值 = 拦截/强制续跑**。简洁的反向控制信号。

## 6. 上下文总会满，必须分四层压缩

**便宜先跑、贵的后跑**：
- L1 `snip`: 裁旧消息（0 API，5ms）
- L2 `micro`: 旧 tool_result 占位（0 API）
- L3 `budget`: 截断超大输出（0 API）
- L4 `auto`: LLM 摘要（1 API，贵）

**关键约束：不能把 `assistant(tool_use)` 和它对应的 `user(tool_result)` 拆开**——模型看不到结果会乱答。

## 7. 记忆和压缩是两件事

- **压缩** = 当前会话的临时裁剪（会丢细节）
- **记忆** = 跨压缩、跨会话的持久文件（不参与压缩）

四类记忆：
- `user`: 你是谁（tab vs space、Chinese preferred）
- `feedback`: 怎么做事（别 mock DB）
- `project`: 当前项目上下文（auth 重写是合规驱动）
- `reference`: 东西在哪（pipeline bug 在 Linear INGEST）

**索引常驻 SYSTEM（被 prompt cache 缓存），文件按需注入当前 user turn（不破坏 cache）**。

## 8. System prompt 是组装出来的，不是写死的

四个 section：
- `identity`（始终）
- `tools`（始终）
- `workspace`（始终）
- `memory`（按需，有文件才注入）

**section 是否加载由真实状态决定**（文件存在？工具启用？），不是消息内容。
相同 hash 缓存复用，命中 prompt cache 省 90% token。

## 9. 长任务必须有 todo（s05）

超过 5 步的任务，模型会"注意力漂移"——做着做着忘了最初目标。
强制它在动手前 `todo_write`，并在循环里加 reminder（3 轮不调就注入提醒）。
TodoWrite 是**当前任务**的执行清单，**任务系统（s12）**是**多目标**的持久化图——别混。

## 10. 子 agent = 干净上下文，丢中间过程

大任务拆成子 agent，每个子 agent 拿：
- 全新 `messages = [task_description]`
- 简化工具集（不能递归 spawn）
- 走完自己的循环

**只回传结论（最后一条 assistant 文本），中间过程全部丢弃**。文件系统的副作用保留。

子 agent 就像"开新终端干一件事，做完关掉"。

## 11. 后台任务 = 慢操作不阻塞主循环

```python
def should_run_in_background(tool, args):
    if args.get("run_in_background"): return True
    return tool == "bash" and "install" in args["command"]
```

慢命令丢 daemon thread，主循环立刻拿到 "Background task started" 占位结果。
后台完成后，下轮 LLM 前把通知注入到 messages。

**主路径是模型显式请求（`run_in_background` 参数），关键词启发式只是兜底。**

## 12. 任务系统 = 持久化 DAG

`TodoWrite` 是当前会话的执行清单。
`Task System` 是 `.tasks/{id}.json` 文件 + `blockedBy` 字段 + 跨会话保留 + 可被认领。

```python
@dataclass
class Task:
    id: str
    subject: str
    status: str  # pending|in_progress|completed
    owner: str | None
    blockedBy: list[str]  # 依赖的任务 ID
    worktree: str | None
```

队友用 `can_start(t) = t.owner is None and all(deps completed)` 找下一个能做的任务。

## 13. 多 agent = 异步邮箱 + 状态机协议

不要做"主从 RPC"。**用文件收件箱（`.jsonl`）异步通信**：
- `BUS.send(fr, to, content, type_)` = 追加一行 JSON
- `BUS.read(agent)` = 读 + 删除（消费式）

**协议 = request_id + 状态机**：
```
Lead: send_request("alice", "shutdown", ...)  # 状态: pending
Alice: dispatch(msg) → handle_shutdown → send_response(request_id, approved=True)
Lead: match_response(msg)  # 状态: approved, 弹出 pending
```

**两个场景用同一套机制**：关机握手、计划审批。

## 14. 自治 = 空闲时轮询，自己认领

队友三阶段生命周期：
- `WORK`: 正常 agent 循环
- `IDLE`: 每 5s 轮询收件箱 + 任务板
- `SHUTDOWN`: 收到 shutdown_request 才退

**idle_poll 5s 间隔 + 60s 超时**。Lead 不用逐个 assign，队友自己 `scan_unclaimed + claim`。

**inbox 优先（可能含 shutdown_request），任务板其次。**

## 15. 并行队友必须 worktree 隔离

Alice 改 `config.py`、Bob 也改 `config.py` → 互相覆盖、无法回滚。
**任务管"做什么"，worktree 管"在哪做"**。

```python
create_worktree(name="auth-refactor", task_id="task_abc")
# → git worktree add .worktrees/auth-refactor -b wt/auth-refactor
# → bind task_abc.worktree = "auth-refactor"
```

队友 `claim_task` 时若 `task.worktree`，自动 `cwd = WORKTREES_DIR / task.worktree`。
**bind 不改状态**——任务还是 `pending`，等队友 idle 时自然认领。

---

## 总结：一句话

**造好 harness：给模型一个最小循环 + 工具池 + 权限边界 + 持久记忆 + 扩展点，让它自己跑。**
不要写工作流，不要写决策树，不要写状态机去"模拟智能"。
**Agency 是训练出来的，你的代码只是给训练好的 agency 一个栖居的世界。**
