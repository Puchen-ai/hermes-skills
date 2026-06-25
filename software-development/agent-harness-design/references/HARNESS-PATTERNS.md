# Harness 模式速查手册（从 learn-claude-code 提炼）

> 来源：https://github.com/shareAI-lab/learn-claude-code (MIT)
> 学习日期：2026-06-25
> 目的：把这套 20 章的 Claude Code 工程模式固化成可复用的设计模式库，下次做 agent 产品时直接套用。

---

## 0. 核心理念（一切机制的地基）

**Agency 来自模型，Harness 让 agency 落地。**

最小循环就是：

```
User → messages[] → LLM → response
                              ↓
              stop_reason == "tool_use" ?
              /                        \
            yes                         no
             |                           |
     execute tools              return text
     append results              (loop ends)
     loop back
```

20 个机制都挂在这个循环上。**循环本身不变，机制是循环周围的装饰**。

格言汇总：
- s01: One loop & Bash is all you need
- s02: 加一个工具, 只加一个 handler
- s03: 工具执行前先做权限判断
- s04: 挂在循环上, 不写进循环里
- s05: 没有计划的 agent 走哪算哪
- s06: 大任务拆小, 每个小任务干净上下文
- s07: 用到时再加载, 别全塞 prompt 里
- s08: 上下文总会满, 要有办法腾地方
- s09: 压缩会丢细节, 要有一层不丢的
- s10: prompt 是组装出来的, 不是写死的
- s11: 错误不是终点, 是重试的起点
- s12: 大目标拆成小任务, 排好序, 持久化
- s13: 慢操作丢后台, agent 继续思考
- s14: 定时触发, 不需要人推
- s15: 一个搞不定, 组队来
- s16: 队友之间要有约定
- s17: 队友自己看板, 有活就认领
- s18: 各干各的目录, 互不干扰
- s19: 能力不够? 插上 MCP
- s20: 机制很多，循环一个

---

## 1. 20 个机制速查表

| ID | 机制 | Harness 层 | 关键代码 | 适用场景 | 复杂度 |
|----|------|----------|---------|---------|-------|
| s01 | Agent Loop | 循环 | `while stop_reason=="tool_use"` | 任何 agent 起手 | ★ |
| s02 | Tool Use | 工具分发 | `TOOL_HANDLERS[block.name]` dispatch map | 多工具 | ★ |
| s03 | Permission | 权限 | 拒绝列表 → 规则匹配 → 用户审批 | 写文件、删文件、跑命令 | ★★ |
| s04 | Hooks | 扩展点 | `register_hook` + `trigger_hooks` 字典 | 日志、审计、注入、修改结果 | ★★ |
| s05 | TodoWrite | 规划 | `TodoItem{content,status}` + reminder 计数 | 复杂多步任务 | ★★ |
| s06 | Subagent | 上下文隔离 | 独立 `messages[]` + 工具受限 | 调研、试错、重活 | ★★ |
| s07 | Skill Loading | 知识 | 启动扫目录注入 SYSTEM + 工具按需加载 | 领域专长、规范 | ★★ |
| s08 | Context Compact | 压缩 | 4 层：snip / micro / budget / auto(LLM) | 长任务、跑大项目 | ★★★ |
| s09 | Memory | 记忆 | `.md` 文件 + `MEMORY.md` 索引 + 4 类型 | 跨会话偏好/项目知识 | ★★★ |
| s10 | System Prompt | 提示组装 | 分段 section + 按需拼装 + 缓存 | 多项目、多工具 | ★★ |
| s11 | Error Recovery | 韧性 | 输出截断升级 / 429-529 退避 / reactive compact | 任何生产 agent | ★★ |
| s12 | Task System | 任务图 | `.tasks/{id}.json` + `blockedBy` DAG | 多目标协同 | ★★★ |
| s13 | Background Tasks | 异步 | daemon thread + `run_in_background` flag | 慢命令、并行 | ★★ |
| s14 | Cron Scheduler | 调度 | 独立线程每秒轮询 + cron 队列 | 周期任务 | ★★★ |
| s15 | Agent Teams | 团队 | MessageBus 文件收件箱 + 队友线程 | 大项目多模块 | ★★★ |
| s16 | Team Protocols | 协议 | `request_id` + 状态机 pending→approved | 关机握手、计划审批 | ★★ |
| s17 | Autonomous Agents | 自治 | idle_poll 5s 轮询 + scan_unclaimed + 自动 claim | 团队扩容 | ★★ |
| s18 | Worktree Isolation | 目录隔离 | git worktree + `task.worktree` 字段 | 并行队友 | ★★★ |
| s19 | MCP Plugin | 插件 | MCPClient + assemble_tool_pool | 接外部服务 | ★★ |
| s20 | Comprehensive | 整合 | 19 个机制挂回同一循环 | 完整产品 | ★★★★ |

---

## 2. 每个机制的最小实现模板

> 以下代码骨架是教学示意，不依赖 Anthropic SDK；接入 Claude API 时把 `call_llm` 换成 `client.messages.create`。

### s01 - Agent Loop（核心，必装）

```python
def agent_loop(messages, system, tools, handlers):
    while True:
        resp = call_llm(messages, system, tools)
        messages.append({"role": "assistant", "content": resp.content})
        if resp.stop_reason != "tool_use":
            return
        results = []
        for block in resp.content:
            if block.type == "tool_use":
                out = handlers[block.name](**block.input)
                results.append({"type": "tool_result", "tool_use_id": block.id, "content": out})
        messages.append({"role": "user", "content": results})
```

### s02 - Tool Use

```python
TOOLS = [{"name": "bash", "description": "...", "input_schema": {...}}, ...]
TOOL_HANDLERS = {"bash": run_bash, "read_file": run_read, ...}
# 在循环里: handlers[block.name](**block.input)
```

### s03 - Permission（拒绝 → 规则 → 询问）

```python
def check_permission(tool, args):
    # 闸门1: 硬拒绝
    if any(d in str(args) for d in DENY_LIST): return "BLOCKED: deny list"
    # 闸门2: 规则匹配
    for rule in PERMISSION_RULES:
        if tool in rule["tools"] and rule["check"](args):
            # 闸门3: 问用户
            if not ask_user(rule["message"]): return "REJECTED by user"
    return None  # None = 放行
```

### s04 - Hooks（4 个事件）

```python
HOOKS = {"UserPromptSubmit": [], "PreToolUse": [], "PostToolUse": [], "Stop": []}
def register_hook(event, fn): HOOKS[event].append(fn)
def trigger_hooks(event, *args):
    for fn in HOOKS[event]:
        r = fn(*args)
        if r is not None and event in ("PreToolUse", "Stop"):
            return r  # 非 None = 拦截 / 强制续跑
# 在循环里: trigger_hooks("PreToolUse", block); out = handler(...); trigger_hooks("PostToolUse", block, out)
```

### s05 - TodoWrite（reminder 3 轮不调就注入提醒）

```python
CURRENT_TODOS = []
def run_todo_write(todos):
    global CURRENT_TODOS; CURRENT_TODOS = todos
    return f"Updated {len(todos)} tasks"
# 循环里: if turns_since_todo > 3: messages.append({"role":"user","content":"[reminder: call todo_write]"})
```

### s06 - Subagent（独立 messages[]）

```python
def spawn_subagent(description, sub_tools, sub_handlers):
    msgs = [{"role": "user", "content": description}]
    for _ in range(30):  # safety limit
        resp = call_llm(msgs, SUB_SYSTEM, sub_tools)
        if resp.stop_reason != "tool_use": break
        results = execute_tool_blocks(resp, sub_handlers, msgs)  # 类似主循环
        msgs.append({"role": "user", "content": results})
    return extract_last_text(msgs)  # 只回传结论
```

### s07 - Skill Loading（目录常驻 + 内容按需）

```python
SKILL_REGISTRY = {}  # name -> {description, content}
def scan_skills():
    for d in SKILLS_DIR.iterdir():
        if (d/"SKILL.md").exists():
            meta, body = parse_frontmatter((d/"SKILL.md").read_text())
            SKILL_REGISTRY[meta["name"]] = {"description": meta["description"], "content": body}
# SYSTEM prompt = identity + "Available skills:\n" + list_skills()
# 工具: load_skill(name) -> SKILL_REGISTRY[name]["content"] (用 tool_result 注入,不塞 SYSTEM)
```

### s08 - Context Compact（4 层，便宜先跑）

```python
def compact(messages):
    messages = snip_compact(messages, max=50)        # L1: 裁旧消息(保 head 3 + tail 47)
    messages = micro_compact(messages, keep=3)       # L2: 旧 tool_result 占位
    if estimate_tokens(messages) > BUDGET:
        messages = budget_compact(messages)          # L3: 截断/裁剪内容
    if estimate_tokens(messages) > BUDGET:
        messages = auto_compact(messages)            # L4: LLM 摘要(1 API)
    return messages
# 关键约束: 不能把 assistant(tool_use) 和 user(tool_result) 拆开
```

### s09 - Memory（4 类: user/feedback/project/reference）

```python
def write_memory(name, type_, description, body):
    (MEMORY_DIR / f"{slug(name)}.md").write_text(
        f"---\nname:{name}\ndescription:{description}\ntype:{type_}\n---\n\n{body}\n"
    )
    rebuild_index()  # MEMORY.md 一行一个链接,注入 SYSTEM
# 加载: build_system() = identity + "\n## Memories\n" + MEMORY.md.read_text()
# 触发: 轮末 extractor 检测 "记住"/稳定偏好 → write_memory
```

### s10 - System Prompt 组装

```python
SECTIONS = {
    "identity": "You are a coding agent. Act, don't explain.",
    "tools": lambda: "Available tools: " + ", ".join(enabled_tools),
    "workspace": f"Working dir: {WORKDIR}",
    "memory": lambda: read_file(MEMORY_FILE) if MEMORY_FILE.exists() else "",
}
def build_system():
    parts = []
    for k in ["identity", "tools", "workspace", "memory"]:
        v = SECTIONS[k]() if callable(SECTIONS[k]) else SECTIONS[k]
        if v: parts.append(f"## {k}\n{v}")
    return "\n\n".join(parts)
# 缓存: system_hash 不变就不重建(命中 prompt cache)
```

### s11 - Error Recovery（3 种恢复模式）

```python
def safe_call_llm(messages, system, tools, state):
    try:
        resp = call_llm(messages, system, tools, max_tokens=8000)
    except PromptTooLong:
        if not state.react_compact:  # reactive compact
            messages = reactive_compact(messages)
            state.react_compact = True
            return safe_call_llm(messages, system, tools, state)  # retry
        raise
    except (RateLimit, Overloaded) as e:
        time.sleep(backoff(state.attempts)); state.attempts += 1
        return safe_call_llm(messages, system, tools, state)
    if resp.stop_reason == "max_tokens":
        if not state.escalated: state.max_tokens = 64000; state.escalated = True
        elif state.cont < 3: messages.append({"role":"user","content":"Resume directly. No apology."})
        return safe_call_llm(messages, system, tools, state)
    return resp
```

### s12 - Task System（DAG + JSON 持久化）

```python
@dataclass
class Task:
    id: str; subject: str; description: str
    status: str  # pending|in_progress|completed
    owner: str | None
    blockedBy: list[str]
    worktree: str | None = None

def create_task(subject, desc="", blockedBy=None):
    t = Task(id=f"task_{int(time.time())}_{randhex(4)}", subject=subject,
             description=desc, status="pending", owner=None, blockedBy=blockedBy or [])
    save_task(t); return t
def claim_task(task_id, agent_name):
    t = load_task(task_id)
    if any(load_task(d).status != "completed" for d in t.blockedBy): return "Blocked"
    if t.owner: return f"Already owned by {t.owner}"
    t.owner, t.status = agent_name, "in_progress"; save_task(t); return f"Claimed by {agent_name}"
def can_start(t): return t.owner is None and all(load_task(d).status=="completed" for d in t.blockedBy)
```

### s13 - Background Tasks（daemon thread）

```python
import threading
def should_background(tool, args):
    if args.get("run_in_background"): return True
    return tool == "bash" and any(kw in args["command"].lower() for kw in
           ["install","build","test","deploy","compile","docker build","npm install","pytest"])
def run_background(tool, args, bg_id):
    threading.Thread(target=lambda: store_result(bg_id, handlers[tool](**args)), daemon=True).start()
# 循环里: if should_background(...): run_background(...); results.append({"content": f"Background {bg_id} started", ...})
# 下轮 LLM 前: 检查完成的后台任务, 注入 messages
```

### s14 - Cron Scheduler（每秒轮询 + 队列）

```python
cron_jobs = []  # {id, cron, prompt, recurring, durable}
cron_queue = []
def scheduler_loop():
    while True:
        now = datetime.now()
        for j in cron_jobs:
            if cron_matches(j["cron"], now) and not j.get("fired_at", now):
                cron_queue.append(j)
                if not j["recurring"]: j["fired_at"] = now
        if j["durable"]: save_jobs(cron_jobs)
        time.sleep(1)
threading.Thread(target=scheduler_loop, daemon=True).start()
# 主循环里: if cron_queue and is_idle(): prompt = cron_queue.pop(0)["prompt"]; inject_and_run(prompt)
```

### s15 - Agent Teams（文件收件箱）

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
def spawn_teammate(name, role, prompt):
    def run():
        msgs = [{"role":"user","content":prompt}]
        for _ in range(10):
            inbox = BUS.read(name)
            if inbox: msgs.append({"role":"user","content":inbox_msgs(inbox)})
            resp = call_llm(msgs, f"You are {name}, a {role}.", sub_tools)
            if resp.stop_reason != "tool_use": break
            msgs.append({"role":"user","content":execute(resp)})
    threading.Thread(target=run, daemon=True).start()
```

### s16 - Team Protocols（request-response + 状态机）

```python
@dataclass
class ProtoState:
    request_id: str; type: str  # "shutdown" | "plan_approval"
    sender: str; target: str
    status: str  # pending|approved|rejected
    payload: str
pending = {}
def send_request(sender, target, type_, payload):
    rid = f"req_{randhex(4)}"
    pending[rid] = ProtoState(rid, type_, sender, target, "pending", payload, time.time())
    BUS.send(sender, target, payload, type_=f"{type_}_request", extra={"request_id": rid})
def dispatch(agent, msg):
    type_ = msg["type"]
    if type_ == "shutdown_request": return handle_shutdown(agent, msg)
    if type_ == "plan_approval_request": return handle_plan(agent, msg)
def match_response(msg):
    rid = msg["request_id"]
    if rid in pending:
        pending[rid].status = "approved" if msg.get("approve") else "rejected"
        return pending.pop(rid)
```

### s17 - Autonomous Agents（idle_poll 5s）

```python
def teammate_lifecycle(agent, msgs, name, role):
    while True:
        # WORK
        resp = call_llm(msgs, f"You are {name}.", sub_tools)
        if resp.stop_reason != "tool_use": break
        msgs.append(execute(resp))
    # IDLE
    for _ in range(60 // 5):
        time.sleep(5)
        inbox = BUS.read(name)
        if any(m["type"] == "shutdown_request" for m in inbox): return "shutdown"
        if inbox: msgs.append(inject(inbox)); return "work"
        unclaimed = [t for t in all_tasks() if t.owner is None and can_start(t)]
        if unclaimed:
            claim_task(unclaimed[0].id, name)
            msgs.append({"role":"user","content":f"Claimed: {unclaimed[0].subject}"})
            return "work"
    return "timeout"
```

### s18 - Worktree Isolation

```python
def create_worktree(name, task_id=""):
    validate_name(name)  # [A-Za-z0-9._-]{1,64}
    path = WORKTREES_DIR / name
    run_git(["worktree", "add", str(path), "-b", f"wt/{name}", "HEAD"])
    if task_id:
        t = load_task(task_id); t.worktree = name; save_task(t)
    return f"Worktree {name} at {path}"
# 队友: claim_task 时若 task.worktree, set wt_ctx["path"] = WORKTREES_DIR/name
# 工具: bash/read/write 在 wt_ctx["path"] 下执行
```

### s19 - MCP Plugin

```python
class MCPClient:
    def __init__(self, name): self.name, self.tools, self._h = name, [], {}
    def register(self, tool_defs, handlers): self.tools, self._h = tool_defs, handlers
    def call(self, name, args): return self._h[name](**args)
def connect_mcp(name):
    factory = MOCK_SERVERS.get(name)  # 真实版:启动子进程,JSON-RPC
    client = factory(); mcp_clients[name] = client
    return f"Connected {name}, tools: {[t['name'] for t in client.tools]}"
def assemble_tool_pool():
    tools = list(BUILTIN_TOOLS)
    for c in mcp_clients.values():
        for t in c.tools: tools.append({**t, "name": f"{c.name}__{t['name']}"})  # 防冲突
    return tools
def dispatch(tool_name, args):
    if "__" in tool_name: srv, tn = tool_name.split("__", 1); return mcp_clients[srv].call(tn, args)
    return TOOL_HANDLERS[tool_name](**args)
```

### s20 - Comprehensive（组件在循环中的位置表）

```
用户输入
  → UserPromptSubmit hooks
  → cron queue + background notifications 注入
  → context compact (4 层)
  → memory + skills + MCP state 组装 system
  → LLM (含 error recovery)
  → has tool_use block?
      no  → Stop hooks → 返回
      yes → PreToolUse + permission
          → tool pool (built-in + MCP)
          → background dispatch (慢操作丢 daemon)
          → handler 执行
          → PostToolUse hooks
          → tool_result 回 messages
          → 下一轮
```

---

## 3. 模式组合建议

| 需求 | 必装机制 | 说明 |
|------|---------|------|
| 最小 demo | s01 + s02 | 一个 bash 工具的循环 |
| 日常 coding | + s03 + s05 | 权限 + 计划 |
| 长任务 | + s04 + s08 + s09 | hooks + 压缩 + 记忆 |
| 长期运行 | + s12 + s14 | 任务图 + 定时 |
| 慢操作多 | + s13 | 后台线程 |
| 多人协作 | + s15 + s16 + s18 | 团队 + 协议 + worktree |
| 自治团队 | + s17 | 队友自己认领 |
| 接外部 | + s19 | MCP |
| 完整产品 | 全部 | 看 s20 |

---

## 4. 立即可用的实操清单

当你下次要"造一个 coding agent"时，按这个顺序搭：

1. 抄 s01 的 20 行循环作为骨架
2. 加 s02 的 TOOL_HANDLERS 字典
3. 加 s03 的三道闸门（在 `handlers[tool]` 之前调用）
4. 加 s04 的 HOOKS（4 个事件）
5. 加 s05 的 todo_write 工具 + reminder
6. 加 s08 的 compact（先只做 L1 + L2）
7. 加 s11 的 error recovery 包裹 LLM 调用
8. 按需加 s06/s07/s09/s10/s12/s13
9. 永远不要改循环本身

**最重要的规矩：扩展行为时挂 hook，不要改 agent_loop。**
