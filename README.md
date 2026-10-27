# C Agent Bundle · 难开口陪练

这是 D 给 C 的**本地 Mock Agent**，用于 C 的视觉提醒/预览工具接入。纯 Python 标准库，不调用真实大模型。

## 快速开始

解压后，在 `c-agent-bundle/` 目录运行：

```bash
python d/agent_server.py --host 127.0.0.1 --port 8000
```

如果解压到团队仓库根目录，则：

```bash
python d/agent_server.py --host 127.0.0.1 --port 8000
```

## C 会用到的接口

```text
POST /api/agent                     开始/回答/结束（与 A 同一契约）
GET  /api/agent/state?session_id=…  C 专用：是否允许视觉提醒
GET  /health                        健康检查
```

## 提醒规则

`reminder_allowed=true` 只在 `state=interviewing`；`reviewing/completed/error` 一律 false。请求失败也按 false 处理。

建议 C 每 300–500ms 查一次，不要每帧请求。C 只做视觉/灯光/震动提醒，不要用语音打断；D 不读取 C 的姿态数据。

## 验证

```bash
python d/test_agent_server.py
```

预期：

```text
AGENT SERVER OK
q_001 -> q_002 -> q_003 -> feedback
reminder_allowed: interviewing=True reviewing=False
```

## 看文档

- `d/docs/c-agent-integration.md`：C 的接入步骤、curl/Python 示例、排障。
- `d/docs/api-contract.md`：完整请求/响应契约。
- `d/schemas/`：机器可读 JSON Schema。
- `d/mock_data/`：主问、两次追问、full/degraded 复盘。

## 边界

- 这是 **Mock**：固定 q_001 → q_002 → q_003 → feedback，不是真实 LLM 出题；C 只依赖字段/状态，不要依赖具体问题文本。
- 真实 Agent 后续替换，接口不变。
- 不传关键点、肩线、摄像头帧给 Agent；视觉数据留在 C。
- 如果提醒跑在设备固件上，由 B 决定 HTTP/串口桥接，不要让 C 直接改引脚或启动逻辑。
