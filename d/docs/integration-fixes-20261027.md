# 联调问题修复记录（2026-10-27）

输入：`D-Agent与真实硬件联调结果_20261027.md`（提交 `a824c67788f867a69a53c52462d5c9c2ea4be95c`）。
修复范围：只改 D 的本地 Mock Agent/文档/测试，不改 B/C 代码，不烧录，不启动对外监听。

## 已修复

### 1. `request_id` 未实现幂等 → 已实现

- 之前：相同 `start_interview` 重发，第二次返回 409。
- 现在：服务按 `(session_id, request_id)` 缓存首次 `(HTTP status, response)`。
  - 相同请求重发直接重放首次响应；
  - 不重复推进状态；
  - 缓存上限 500 条，`reset_sessions()` 一并清空。
- 覆盖：重复 `start_interview`、重复 `submit_answer` 均返回同一响应，不产生第二次副作用。

### 2. `retry` 未清空上一轮回答 → 已修复

- 之前：`retry` 只重置 `turn` 和 `last_question_id`，`answers` 保留；重练后不回答直接 `end_interview` 仍返回 full。
- 现在：
  - `retry` 只允许在 `reviewing`；
  - 上一轮 `answers` 进入 `history`；
  - `attempt += 1`，`answers = []`；
  - `state` 回到 `interviewing`，`last_question_id=q_001`；
  - 重练后不回答直接结束 → `degraded`。
- `/api/agent/state` 新增 `attempt`、`round_answers`，C/B 不再只能靠 `state` 字符串区分重练。

## 验证

```bash
python d/test_agent_server.py
```

实际输出：

```text
AGENT SERVER OK
  q_001 -> q_002 -> q_003 -> feedback
  idempotency: start/answer replay OK
  retry: attempt=2 round_answers=0 end_mode=degraded
  reminder_allowed: interviewing=True reviewing=False
```

```bash
python d/test_agent_flow.py
```

仍输出 `VALIDATION OK`。

## 仍未完成（不能冒充已通过）

- 设备语音直连、ASR/TTS：未实现；当前 D 是电脑本地 HTTP 文本 Mock。
- B 的 HTTP/串口桥接位置：未实现；`127.0.0.1` 只在本机有效。
- 真实模型/灵机平台能力调用：未实现。
- 灯圈/震动/语音视觉并发：未做实物验收。
- B/D 状态映射表（`project_selected→PREPARE` 等）仍是提案，未改 B 固件。

## 相关文件

```text
d/agent_server.py
d/test_agent_server.py
d/docs/api-contract.md
d/docs/c-agent-integration.md
d/docs/a-agent-handoff.md
```
