
# Changelog

## 2026-06-25 (v2.0 - 10 轮反复打磨后)

### 改了什么
- 重写 SKILL.md: 从 README 式综述 → 30 分钟可读的精华速查
- 新增第 10 节 "完整示例": 不依赖 API key 跑通最小 harness
- 新增 ANTIPATTERNS.md: 20 条反模式 (从 s20 注释提炼)
- 新增 hello_world_agent.py: 实测可运行的最小例子

### 关键洞察增量
- **s20 增量**: 抽出 RecoveryState 类, with_retry 包裹 LLM, prepare_context 整合 4 层
- **s20 新层 L0**: tool_result_budget 持久化大输出 (s08 没这层)
- **s20 修正**: has_tool_use 替代 stop_reason (永远看事实不看自报)
- **s20 真正门控**: protocol_ctx["waiting_plan"] 时间维度阻断 model
- **s20 主动 compact**: 模型可显式调 compact 工具, 不只等超限

### 之前的 1.0 版内容保留在 references
- HARNESS-PATTERNS.md (18KB, 完整速查)
- KEY-INSIGHTS.md (7KB, 15 条精华)

### 自我验证
- ✅ 跑通 s01 循环 mock (2 轮 tool_use → end_turn)
- ✅ 跑通 hello_world_agent.py (写文件 → 跑命令 → 输出)
- ✅ Python 3.6/3.8 兼容 (Path.is_relative_to 替代为 relative_to try/except)
