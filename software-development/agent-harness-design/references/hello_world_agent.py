"""
教学示例：Hello World Agent
- 最小可用 harness (s01 + s02 + s04 hooks)
- 5 个工具: bash / read_file / write_file / edit_file / glob
- 1 个 hook: PreToolUse 日志
- 不依赖 API key (使用 mock LLM)
- 跑一次完整任务: "创建 hello.py, 写个 hello world 函数, 运行它"

这是 s20 的最小可运行演示, 删掉了 s05-s19 所有复杂机制。
"""
import os, subprocess, json
from pathlib import Path

# ── 工具定义 (s02) ──
TOOLS = [
    {"name": "bash", "description": "Run a shell command.",
     "input_schema": {"type": "object", "properties": {"command": {"type": "string"}}, "required": ["command"]}},
    {"name": "read_file", "description": "Read a file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}},
    {"name": "write_file", "description": "Write a file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "content": {"type": "string"}}, "required": ["path", "content"]}},
    {"name": "edit_file", "description": "Replace text in a file.",
     "input_schema": {"type": "object", "properties": {"path": {"type": "string"}, "old_text": {"type": "string"}, "new_text": {"type": "string"}}, "required": ["path", "old_text", "new_text"]}},
    {"name": "glob", "description": "Find files by glob pattern.",
     "input_schema": {"type": "object", "properties": {"pattern": {"type": "string"}}, "required": ["pattern"]}},
]

# ── 工具实现 (s02) ──
WORKDIR = Path.cwd()

def safe_path(p):
    path = (WORKDIR / p).resolve()
    # Python 3.6/3.8 兼容: 没有 Path.is_relative_to
    try:
        path.relative_to(WORKDIR)
    except ValueError:
        raise ValueError(f"Path escapes workspace: {p}")
    return path

def run_bash(command):
    dangerous = ["rm -rf /", "sudo", "shutdown", "reboot"]
    if any(d in command for d in dangerous):
        return "Error: Dangerous command blocked"
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=10, cwd=WORKDIR)
        out = (r.stdout + r.stderr).strip()
        return out[:10000] if out else "(no output)"
    except Exception as e:
        return f"Error: {e}"

def run_read(path):
    try:
        return safe_path(path).read_text()[:10000]
    except Exception as e:
        return f"Error: {e}"

def run_write(path, content):
    try:
        fp = safe_path(path); fp.parent.mkdir(parents=True, exist_ok=True); fp.write_text(content)
        return f"Wrote {len(content)} bytes to {path}"
    except Exception as e:
        return f"Error: {e}"

def run_edit(path, old_text, new_text):
    try:
        fp = safe_path(path); text = fp.read_text()
        if old_text not in text: return f"Error: text not found in {path}"
        fp.write_text(text.replace(old_text, new_text, 1))
        return f"Edited {path}"
    except Exception as e:
        return f"Error: {e}"

def run_glob(pattern):
    import glob as g
    return "\n".join(g.glob(pattern, root_dir=WORKDIR)) or "(no matches)"

# ── Dispatch map (s02 关键模式) ──
TOOL_HANDLERS = {
    "bash": lambda command: run_bash(command),
    "read_file": lambda path: run_read(path),
    "write_file": lambda path, content: run_write(path, content),
    "edit_file": lambda path, old_text, new_text: run_edit(path, old_text, new_text),
    "glob": lambda pattern: run_glob(pattern),
}

# ── Hooks (s04) ──
HOOKS = {"PreToolUse": [], "PostToolUse": [], "Stop": []}
def register_hook(event, fn): HOOKS[event].append(fn)
def trigger_hooks(event, *args):
    for fn in HOOKS[event]:
        r = fn(*args)
        if r is not None: return r
    return None

def log_hook(block):
    print(f"  [hook] {block['name']}({json.dumps(block['input'])[:60]})")
    return None

register_hook("PreToolUse", log_hook)

# ── Mock LLM (代替真 LLM) ──
class MockBlock:
    def __init__(self, type, name=None, input=None, text=None):
        self.type = type
        self.name = name
        self.input = input or {}
        self.text = text or ""

class MockResp:
    def __init__(self, content, stop_reason):
        self.content = content
        self.stop_reason = stop_reason

# 任务: "创建 hello.py, 写个 hello world 函数, 跑一下"
# 脚本化的"模型行为": 4 步
SCRIPT = [
    MockResp([
        MockBlock("tool_use", "write_file", {"path": "hello.py", "content": "def hello():\n    return 'Hello, World!'\n\nif __name__ == '__main__':\n    print(hello())\n"}),
    ], "tool_use"),
    MockResp([
        MockBlock("tool_use", "bash", {"command": "python hello.py"}),
    ], "tool_use"),
    MockResp([
        MockBlock("text", text="✅ 已创建 hello.py 并运行, 输出 'Hello, World!'")
    ], "end_turn"),
]

# ── Agent Loop (s01) ──
def has_tool_use(content):
    return any(b.type == "tool_use" for b in content)

def agent_loop(messages):
    idx = 0
    rounds = 0
    while idx < len(SCRIPT):
        response = SCRIPT[idx]; idx += 1
        messages.append({"role": "assistant", "content": [
            {"type": b.type, "text": b.text, "name": b.name, "input": b.input}
            for b in response.content
        ]})
        if not has_tool_use(response.content):
            trigger_hooks("Stop", messages)
            return rounds
        results = []
        for block in response.content:
            if block.type != "tool_use": continue
            block_dict = {"name": block.name, "input": block.input}
            blocked = trigger_hooks("PreToolUse", block_dict)
            if blocked:
                out = str(blocked)
            else:
                handler = TOOL_HANDLERS.get(block.name)
                if handler:
                    out = handler(**block.input)
                else:
                    out = f"Unknown tool: {block.name}"
            trigger_hooks("PostToolUse", block_dict, out)
            print(f"  → {out[:100]}")
            results.append({"type": "tool_result", "tool_use_id": f"id_{rounds}_{block.name}", "content": out})
        messages.append({"role": "user", "content": results})
        rounds += 1
    return rounds

# ── 跑 ──
if __name__ == "__main__":
    print("=" * 50)
    print("Hello World Agent - 教学示例")
    print("= s01 (循环) + s02 (dispatch) + s04 (hooks) =")
    print("=" * 50)
    print(f"\n工作目录: {WORKDIR}")
    print(f"任务: 创建 hello.py, 写 hello world 函数, 跑它\n")
    messages = [{"role": "user", "content": "创建一个 hello.py, 写个 hello world 函数, 跑一下"}]
    rounds = agent_loop(messages)
    print(f"\n✅ 完成 {rounds} 轮工具调用")
    # 显示最终文件
    if (WORKDIR / "hello.py").exists():
        print(f"\n📄 hello.py 内容:")
        print((WORKDIR / "hello.py").read_text())
