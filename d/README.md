# D · 面试 Agent、产品验收与展示

当前提供 D↔A 的接口基线、Mock 数据和最小验证脚本；真实模型调用/后端服务尚未接入。

## 本次交付

| 路径 | 内容 |
|---|---|
| `d/docs/api-contract.md` | D→A 接口契约：状态流转、请求/响应 JSON、追问/反馈字段 |
| `d/docs/a-agent-handoff.md` | 给 A 的 GPT-6.1 Sol 工作说明（可粘贴提示词、实现顺序、确认项） |
| `d/schemas/` | A/D 请求与响应的机器可读 JSON Schema |
| `d/mock_data/` | 1 个项目 + 主问 + 2 次追问 + full/degraded 复盘，共 5 个请求/响应回合 |
| `d/prompts/interviewer_system_prompt.md` | 资深嵌入式面试官 System Prompt（文本-only） |
| `d/test_agent_flow.py` | 纯标准库验证脚本，模拟 A→D→A 并校验契约 |
| `d/agent_server.py` | 本地 Mock HTTP Agent（`POST /api/agent` + `/api/agent/state`） |
| `d/docs/c-agent-integration.md` | C 接入说明：提醒仲裁、curl/Python 示例 |
| `d/test_agent_server.py` | 启动本地服务并走 HTTP 流程的验证脚本 |

## 运行

```bash
python d/test_agent_flow.py
python d/test_agent_server.py
```

预期输出：`VALIDATION OK` 和 `AGENT SERVER OK`，退出码 0。

本地给 C 联调：

```bash
python d/agent_server.py --host 127.0.0.1 --port 8000
```

C 的提醒前先查 `GET /api/agent/state?session_id=...`，只在 `reminder_allowed=true` 时提醒。

## 边界

- 第一版不消费 C 的视觉/姿态数据，仅基于项目字段和文本回答。
- 不做录用预测、性格/情绪判断、分数；复盘只引用实际回答。
- A 的接口确认项见 `d/docs/api-contract.md` 第 5 节。
