# 20 条反模式 (从 s20 code.py 注释和踩坑提炼)

> 来源: 通读 s20 2123 行 + 反复对比 s01-s19 各章后总结

## 表格速查

| # | 反模式 | 为什么错 | 正解 |
|---|--------|---------|------|
| 1 | 把 tool_result 拆成前后两半 | 模型看不到结果会乱答 | snip 时检查 `message_has_tool_use` 边界 |
| 2 | 用 `stop_reason` 判断继续 | 模型给的"自报"不可靠 | `has_tool_use(content)` 看事实 |
| 3 | 队友线程里 spawn 另一个 | 上下文会爆 | spawn 只能从 Lead 发起 |
| 4 | bash 输出截断丢掉 | 大输出可能含关键错误 | 50000 限制 + 持久化文件 + 路径+预览 |
| 5 | cron 同分钟重复触发 | `0 9 * * *` 一秒内 60 次 | `_last_fired[id] != marker` 分钟级去重 |
| 6 | memory 全文塞 SYSTEM | 1k memory = 100k token | MEMORY.md 索引常驻, 文件按需注入 |
| 7 | 压缩后丢原始 transcript | debug 时找不到现场 | 先 `write_transcript` 存盘再摘要 |
| 8 | 队友读 inbox 不删 | 反复读同一封 | `inbox.unlink()` 消费式 |
| 9 | submit_plan 后续 tool_use 不阻断 | 计划未批就执行 | `protocol_ctx["waiting_plan"]` 门控 |
| 10 | write_file 不限工作区 | 改 /etc 风险 | `safe_path` 强校验 |
| 11 | worktree 名 `..` 路径穿越 | 跳出工作区 | `^[A-Za-z0-9._-]{1,64}$` 严格白名单 |
| 12 | SYSTEM 整段拼字符串 | 加段冲突 | sections 字典 + 运行时拼装 |
| 13 | 用普通变量当恢复状态 | 散落难追踪 | `RecoveryState` 类统一 |
| 14 | 阻塞 LLM 等慢操作 | `pip install` 等 10 分钟 | daemon thread + task_notification |
| 15 | Skill 全文塞 SYSTEM | 6.5k 行浪费 | 目录清单常驻, 工具按需加载 |
| 16 | 队友做完就退 | 团队利用率低 | IDLE 5s 轮询, 60s 没事才退 |
| 17 | permissions 写进 if-else | 循环成屎山 | `permission_hook` 单独函数, 注册 hook |
| 18 | 主循环嵌所有逻辑 | 不可维护 | 5 行做循环, 5 个机制挂 5 个 hook |
| 19 | Subagent 反复"对话" | 浪费 token, 永不停 | 给子 agent `for _ in range(30)`, 只回传最后 text |
| 20 | todo 提醒太频繁 | 模型烦 | 3 轮(约 9 步)没调才注入 reminder |

## 详细解释

### #1 - 不拆 tool_result
```python
# 错
if len(messages) > 50:
    messages = messages[:3] + messages[-47:]  # 可能把 assistant(tool_use) 和 user(tool_result) 拆开

# 对
def snip_compact(messages, max_messages=50):
    if len(messages) <= max_messages: return messages
    head_end, tail_start = 3, len(messages) - (max_messages - 3)
    # 边界保护: 如果 head_end 处是 tool_result, 后退
    if head_end > 0 and message_has_tool_use(messages[head_end - 1]):
        while head_end < len(messages) and is_tool_result_message(messages[head_end]):
            head_end += 1
    # 边界保护: 如果 tail_start 处是 tool_result, 前进
    if tail_start > 0 and tail_start < len(messages) and is_tool_result_message(messages[tail_start]) and message_has_tool_use(messages[tail_start - 1]):
        tail_start -= 1
    return messages[:head_end] + [{"role":"user","content":f"[snipped {tail_start-head_end} msgs]"}] + messages[tail_start:]
```

### #2 - has_tool_use 替代 stop_reason
```python
# 错: 依赖模型自报
if response.stop_reason == "tool_use": continue

# 对: 看 content 事实
def has_tool_use(content):
    return any(getattr(b, "type", None) == "tool_use" for b in content)
if not has_tool_use(response.content): return  # 退出
```

### #4 - bash 输出持久化
```python
# 错
out = r.stdout[:5000]  # 截断, 丢信息

# 对
PERSIST_THRESHOLD = 30000
def persist_large_output(tool_use_id, output):
    if len(output) <= PERSIST_THRESHOLD: return output
    path = TOOL_RESULTS_DIR / f"{tool_use_id}.txt"
    if not path.exists(): path.write_text(output)
    return f"<persisted-output>Full: {path}\nPreview: {output[:2000]}</persisted-output>"
```

### #9 - submit_plan 门控
```python
# 错: 队友 submit_plan 之后模型继续调工具
# 对 (s20 才实现)
protocol_ctx = {"waiting_plan": None}
# 在循环里:
for block in response.content:
    if block.type == "tool_use":
        if block.name == "submit_plan":
            output = _submit_plan(name, block.input.get("plan"))
            protocol_ctx["waiting_plan"] = extract_request_id(output)
        else:
            output = handlers[block.name](**block.input)
        results.append(...)
        if protocol_ctx["waiting_plan"]:
            break  # 忽略后续 tool_use, 等审批

# 下轮 LLM 前:
if protocol_ctx["waiting_plan"]:
    time.sleep(5); continue  # 跳过 model call, 纯轮询
```

### #14 - 后台任务
```python
# 错
def run_bash(command):  # 同步, 等 10 分钟
    r = subprocess.run(command, shell=True, timeout=600)
    return r.stdout

# 对
def should_run_background(tool, args):
    if args.get("run_in_background"): return True
    return tool == "bash" and "install" in args["command"]  # 关键词兜底

# 循环里:
if should_run_background(block.name, block.input):
    bg_id = start_background_task(block, handlers)
    results.append({"type": "tool_result", "content": f"Background {bg_id} started. Result arrives as task_notification."})
    continue
```

### #18 - 主循环的 5 行骨架
```python
# 错: 50 行的循环
def agent_loop(messages):
    while True:
        response = client.messages.create(...)
        messages.append(...)
        if response.stop_reason != "tool_use": return
        for block in response.content:
            if block.type != "tool_use": continue
            # 权限检查
            if block.name == "bash" and "rm" in block.input["command"]: ...
            # 日志
            print(block.name)
            # 慢操作
            if "install" in block.input["command"]: ...
            # 大输出检查
            out = HANDLERS[block.name](**block.input)
            if len(out) > 100000: print(...)
            # 执行
            results.append(...)
        messages.append(results)

# 对: 5 行做循环, 机制挂 hook
def agent_loop(messages, call_llm, handlers):
    while True:
        response = call_llm(messages)
        messages.append(as_message(response))
        if not has_tool_use(response.content): return
        results = []
        for block in tool_use_blocks(response):
            if (b := trigger_hooks("PreToolUse", block)):
                out = b
            else:
                out = handlers[block.name](**block.input)
            trigger_hooks("PostToolUse", block, out)
            results.append(tool_result(block, out))
        messages.append(as_user(results))
```
