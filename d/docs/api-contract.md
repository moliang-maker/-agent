# D ↔ A 接口契约：面试 Agent

- 契约版本：`1.0`
- 日期：2026-10-27
- Owner：D（面试 Agent、题目与反馈）
- 调用方：A（网页、会话状态、复盘界面）
- 范围：**纯文本**面试问答；第一版不消费 C 的视觉数据，不依赖摄像头/姿态结果。

本文是 D 与 A 的接口基线。字段名、枚举值、状态流转以本文为准；变更需升版本并同步 A。

## 0. 端点

| 端点 | Owner | 说明 |
|---|---|---|
| `POST /api/agent` | D（当前 A 侧先留占位） | 本契约的 Agent 请求/响应 |
| `GET /api/agent/state?session_id=...` | D | C 提醒仲裁用；A 可不调用，详见 `d/docs/c-agent-integration.md` |
| `POST /api/resume/parse` | A | 简历解析，保持 A 现有接口；D 不调用 |

A 已确认使用 `POST /api/agent` 和原生 `fetch`；当前项目尚未实现该接口，联调前可先用 `d/mock_data/` 做前端夹具。

---

## 1. 一次完整面试的状态流转

```text
waiting_resume
  │  A 上传简历并让用户确认一个项目
  ▼
project_selected
  │  A 发 action=start_interview
  ▼
interviewing ── A 发 submit_answer ──► interviewing（继续提问/追问）
  │                                      │
  │                                      └─ 主问/追问预算用完，D 返回 feedback
  ▼
reviewing
  │  A 渲染反馈；用户选择重练或结束
  ├─ action=retry ──► interviewing
  └─ action=complete_session ──► completed
```

| 状态 | 谁驱动 | 含义 | A 的页面 |
|---|---|---|---|
| `waiting_resume` | A | 还没有确认项目 | 上传/解析页 |
| `project_selected` | A | 用户已确认一个项目，可开始 | 项目确认页 |
| `interviewing` | D | D 正在提问/追问，等待用户回答 | 面试页 |
| `reviewing` | D | D 已返回复盘，等待 A 展示 | 复盘页 |
| `completed` | A | 用户结束/保存 | 完成页 |
| `error` | D | 可恢复或不可恢复错误 | 错误提示 |

规则：
- D 在每次响应里返回 `state`；A 以响应里的 `state` 为准，不自行推断。
- `type=question` 只出现在 `interviewing`。
- `type=feedback` 只出现在 `reviewing`（`complete_session` 后 A 本地置为 `completed`）。
- `type=error` 可出现在任意状态；`recoverable=true` 时 A 可重试同一 `request_id`。

---

## 2. A → D 请求

### 2.1 请求字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `contract_version` | string | 是 | 固定 `"1.0"` |
| `request_id` | string | 是 | A 生成，幂等；重试必须复用 |
| `session_id` | string | 是 | A 生成并保存，整场不变；建议 `crypto.randomUUID()`，字段名固定 `session_id` |
| `action` | enum | 是 | `start_interview` / `submit_answer` / `end_interview` / `retry` / `complete_session` |
| `state` | enum | 是 | 发送时 A 认为的状态，见第 1 节 |
| `project` | object | `start_interview` 必填 | 已确认项目，见 2.2 |
| `answer` | object/null | `submit_answer` 必填 | 用户回答，见 2.3 |
| `retry` | object/null | `retry` 必填 | `{ "question_id": "q_001" }` |
| `client` | object | 否 | `{ "source": "web", "user_confirmed": true }` |

### 2.2 `project` 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `name` | string | 是 | 项目名称 |
| `description` | string | 是 | 项目描述：背景、目标、技术方案 |
| `role` | string | 是 | 用户角色，如“嵌入式软件” |
| `tech_stack` | string[] | 否 | 技术栈 |
| `responsibilities` | string[] | 否 | 用户个人职责 |
| `metrics` | object[] | 否 | `[{name,value,unit}]` |
| `resume_evidence` | string | 否 | 简历原文引用 |

说明：`description` 必须是非空文本；D 不用它编造用户经历，只用于出题与引用。

### 2.3 `answer` 字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `turn_id` | string | 是 | 回答的是哪一问；用上一次响应里的 `question.turn_id` |
| `text` | string | 是 | ASR 最终文本或用户订正后的文本 |
| `duration_ms` | integer | 否 | 回答时长，用于产品观察 |
| `asr_confidence` | number | 否 | 0–1；低置信度时 D 可要求重说 |

### 2.4 请求示例

```json
{
  "contract_version": "1.0",
  "request_id": "req_0001",
  "session_id": "3f2a7c1e-9b4d-4c6a-8e21-7d5f0a9b2c34",
  "action": "start_interview",
  "state": "project_selected",
  "project": {
    "name": "基于STM32的云台控制系统",
    "description": "为机器视觉实验做二轴云台，负责电机控制与CAN通信。",
    "role": "嵌入式软件",
    "tech_stack": ["STM32F407", "FreeRTOS", "CAN", "PID"],
    "responsibilities": ["电机控制", "CAN通信", "PID整定"],
    "metrics": [{"name": "超调", "value": "8", "unit": "%"}],
    "resume_evidence": "负责云台电机控制与CAN通信，PID整定后超调降至8%。"
  },
  "answer": null,
  "client": {"source": "web", "user_confirmed": true}
}
```

---

## 3. D → A 响应

### 3.1 通用响应字段

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `contract_version` | string | 是 | `"1.0"` |
| `request_id` | string | 是 | 与请求一致 |
| `session_id` | string | 是 | 与请求一致 |
| `state` | enum | 是 | `interviewing` / `reviewing` / `completed` / `error` |
| `type` | enum | 是 | **`question` / `feedback` / `error`** |
| `question` | object/null | `type=question` 时必填 | 见 3.2 |
| `feedback` | object/null | `type=feedback` 时必填 | 见 3.3 |
| `error` | object/null | `type=error` 时必填 | 见 3.4 |
| `meta` | object | 是 | `{turn_index,max_turns,elapsed_seconds}` |

### 3.2 `question`（提问/追问）

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `turn_id` | string | 是 | 本次问题 ID，A 回答时回传 |
| `kind` | enum | 是 | `main` / `followup` |
| `text` | string | 是 | 展示文本 |
| `tts_text` | string | 是 | 语音文本，≤45 个中文字符 |
| `is_followup` | boolean | 是 | **是否追问**；主问 false，追问 true |
| `parent_turn_id` | string/null | 追问必填 | 追的是哪一问 |
| `followup_reason` | string/null | 追问必填 | `ownership` / `data` / `boundary` / `process` / `contradiction` / `mechanism` / `scope` 等 |
| `target_rule` | string/null | 追问必填 | 规则 ID，如 `P01` / `E01` / `T04` |
| `expected_focus` | string | 否 | 这一问想听到什么 |
| `max_answer_seconds` | integer | 否 | 默认 90 |

### 3.3 `feedback`（复盘结果）

`type=feedback` 时，`question=null`，`state=reviewing`。

| 字段 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `mode` | enum | 是 | `full` / `degraded` |
| `summary` | string | 是 | 一句话总结，不评分、不预测录用 |
| `items` | object[] | 是 | 最多 3 条；每条见下 |
| `items[].item_id` | string | 是 | 条目 ID |
| `items[].turn_id` | string | 是 | 对应问题 |
| `items[].quote` | string | 是 | **回答原文子串**，不得改写 |
| `items[].issue_type` | string | 是 | 问题类型，如 `ownership` / `data` |
| `items[].issue` | string | 是 | 具体问题 |
| `items[].suggestion` | string | 是 | 可执行建议 |
| `items[].severity` | enum | 是 | `P0` / `P1` / `P2` |
| `strengths` | object[] | 否 | `[{quote,point}]`，最多 2 条 |
| `retry_plan` | object/null | 否 | `{question_id,instruction}`；degraded 时为 null |
| `next_action` | string | 是 | 下一步建议 |
| `quotes_verified` | boolean | 是 | 引用是否已校验；degraded 无用户引用时为 false |
| `notice` | object/null | degraded 必填 | 给 A 的单一提示，字段与 item 对齐 |
| `notice.quote` | string | degraded 必填 | **系统提示文案，不是用户原话** |
| `notice.issue` | string | degraded 必填 | 发生了什么 |
| `notice.suggestion` | string | degraded 必填 | 用户下一步动作 |
| `notice.severity` | enum | degraded 必填 | 固定 `"info"` |

`mode=degraded` 时：`items=[]`、`strengths=[]`、`retry_plan=null`，只给 `summary`、`notice` 与 `next_action`，不评判能力。A 可复用 `quote/issue/suggestion/severity` 的渲染组件展示 `notice`；不要把 `notice.quote` 当成用户原话。

degraded 示例：

```json
"feedback": {
  "mode": "degraded",
  "summary": "暂时没有识别到完整回答。",
  "items": [],
  "strengths": [],
  "retry_plan": null,
  "next_action": "请重新回答，或稍后再试。",
  "quotes_verified": false,
  "notice": {
    "quote": "暂时没有识别到完整回答",
    "issue": "语音识别或 Agent 服务暂时不可用",
    "suggestion": "请重新回答，或稍后再试",
    "severity": "info"
  }
}
```

### 3.4 `error`

```json
{
  "error": {
    "code": "E_PROJECT_INCOMPLETE",
    "message": "项目描述为空，请先补充。",
    "recoverable": true
  }
}
```

错误码至少包括：`E_BAD_REQUEST`、`E_STATE_CONFLICT`、`E_PROJECT_INCOMPLETE`、`E_PROJECT_UNCONFIRMED`、`E_RESUME_NOT_TEXT`、`E_ASR_EMPTY`、`E_TIMEOUT`、`E_LLM_INVALID`、`E_UNSUPPORTED`、`E_INTERNAL`。

### 3.5 成功响应示例（提问）

```json
{
  "contract_version": "1.0",
  "request_id": "req_0001",
  "session_id": "3f2a7c1e-9b4d-4c6a-8e21-7d5f0a9b2c34",
  "state": "interviewing",
  "type": "question",
  "question": {
    "turn_id": "q_001",
    "kind": "main",
    "text": "先用一分钟介绍这个项目，以及你个人负责的部分。",
    "tts_text": "先用一分钟介绍这个项目，以及你个人负责的部分。",
    "is_followup": false,
    "parent_turn_id": null,
    "followup_reason": null,
    "target_rule": null,
    "expected_focus": "项目背景与个人贡献",
    "max_answer_seconds": 90
  },
  "feedback": null,
  "error": null,
  "meta": {"turn_index": 1, "max_turns": 6, "elapsed_seconds": 0}
}
```

### 3.6 成功响应示例（追问）

```json
{
  "contract_version": "1.0",
  "request_id": "req_0002",
  "session_id": "3f2a7c1e-9b4d-4c6a-8e21-7d5f0a9b2c34",
  "state": "interviewing",
  "type": "question",
  "question": {
    "turn_id": "q_002",
    "kind": "followup",
    "text": "你刚才说“我们团队”，其中哪部分是你亲自做的？",
    "tts_text": "你刚才说“我们团队”，哪部分是你亲自做的？",
    "is_followup": true,
    "parent_turn_id": "q_001",
    "followup_reason": "ownership",
    "target_rule": "P01",
    "expected_focus": "个人贡献边界",
    "max_answer_seconds": 90
  },
  "feedback": null,
  "error": null,
  "meta": {"turn_index": 2, "max_turns": 6, "elapsed_seconds": 22}
}
```

### 3.7 成功响应示例（复盘）

```json
{
  "contract_version": "1.0",
  "request_id": "req_0004",
  "session_id": "3f2a7c1e-9b4d-4c6a-8e21-7d5f0a9b2c34",
  "state": "reviewing",
  "type": "feedback",
  "question": null,
  "feedback": {
    "mode": "full",
    "summary": "能给出结果数据，但个人贡献的边界还不够清楚。",
    "items": [
      {
        "item_id": "it_01",
        "turn_id": "q_001",
        "quote": "我们团队",
        "issue_type": "ownership",
        "issue": "用“我们团队”代替了个人贡献。",
        "suggestion": "用“我负责…，具体做了…，交付了…”重讲。",
        "severity": "P0"
      }
    ],
    "strengths": [
      {"quote": "超调从 15% 降到 8%", "point": "给出了可量化的结果。"}
    ],
    "retry_plan": {"question_id": "q_001", "instruction": "重讲一次，先说你个人负责的部分。"},
    "next_action": "按建议重练 q_001。",
    "quotes_verified": true
  },
  "error": null,
  "meta": {"turn_index": 3, "max_turns": 6, "elapsed_seconds": 95}
}
```

---

## 4. 约束与校验

1. 一次只问一个问题；`tts_text` ≤45 个中文字符，问号 ≤1。
2. 主问最多 3 个，每个主问最多 2 次追问；总提问最多 6 个（`max_turns=6`）。
3. `is_followup=true` 时必须有 `parent_turn_id`、`followup_reason`、`target_rule`。
4. 复盘 `items` ≤3；每条 `quote` 必须是所引用回答的原文子串；`quotes_verified=true` 才能展示。
5. 不编造经历、数字、成果；不把“参与/协助”写成“主导/独立负责”。
6. 不做录用预测、性格/情绪判断；不输出分数、offer 建议。
7. 第一版不使用 C 的视觉数据；A 不需要传摄像头/姿态字段。
8. 重试：同一 `request_id` 重发必须幂等；A 超时后最多重试 1 次。
9. 契约版本变更：新增可选字段升 `1.1`；破坏性变更升 `2.0`，提前通知 A。
10. 幂等实现：同一 `(session_id, request_id)` 只执行一次，重放相同的 HTTP 状态和响应；重复 `start_interview` 不应返回 409。
11. 重练轮次：只有 `reviewing` 可 `retry`；`retry` 开启新 attempt，清空本轮 `answers`，上一轮进入 `history`；`state` 仍是 `interviewing`，用 `/api/agent/state` 的 `attempt`、`round_answers` 区分轮次。

---

## 5. A 使用 GPT-6.1 Sol 工作

A 使用 **GPT-6.1 Sol** 作为编码/联调工作模型。给模型的可粘贴交接说明、必须保持的 6 个点和 A 侧实现顺序见：

```text
d/docs/a-agent-handoff.md
```

机器可读 schema：

```text
d/schemas/agent_request.schema.json
d/schemas/agent_response.schema.json
```

wire format 不变；模型不要新增视觉字段或改写 D 的契约。

## 6. A 已确认的决定

| 项 | A 的决定 |
|---|---|
| Agent 端点 | `POST /api/agent`（当前项目尚未实现，后续补） |
| 简历解析端点 | `POST /api/resume/parse`（A 现有接口，D 不调用） |
| 请求方式 | 原生 `fetch`，暂不引入 axios |
| 全局状态 | 至少 `session_id`、`resumeParsed`、`candidateName`、`practiceProject` |
| 适配层 | A 提供 `agentAdapter`，把 `practiceProject` 转成 D 的 `project`；D 不直接依赖 A 字段 |
| `session_id` | A 在新建练习时生成，建议 `crypto.randomUUID()`；字段名固定 `session_id` |
| 错误 Toast | 普通错误显示 2200ms |
| 超时 | 10 秒；提示“Agent 请求超时，请稍后重试”；用 `AbortController` |
| 复盘字段 | 按 `quote/issue/suggestion/severity` 渲染 |
| degraded | A 需要；D 已补 `feedback_degraded.json` + `notice` 字段 |

以下由 D 决定，**不需要 A 确认**：

| 项 | D 的默认决定 |
|---|---|
| `project.description` 怎么拼 | A 的 adapter 可自由拼 `professional/target/technicalPlan/debugging/result`；D 只要求非空文本，且是用户确认过的内容 |
| `session_id` 格式 | 任意不透明字符串均可；A 用 `crypto.randomUUID()` 就行，D 不校验前缀 |
| `severity` 的颜色/标签 | D 只定义 `P0/P1/P2/info`；A 自己映射颜色 |
| `E_TIMEOUT` 等错误 mock | D 可按需补，不阻塞 A；A 先处理 `error.message + recoverable` |
| 全局状态库/Toast 组件 | A 内部实现，D 不依赖 |
| `agentAdapter` 具体写法 | A 拥有；D 只规定输出 `project` 字段 |

真正需要 A 在联调时确认的只有 2 条：
- [ ] A 能否在 `submit_answer` 回传上一问的 `question.turn_id`（契约硬要求）。
- [ ] A 的复盘组件能否渲染 degraded 的 `feedback.notice`（复用 `quote/issue/suggestion/severity`）。

### 6.1 A 的项目状态结构（A 侧）

```js
{
  session_id: "",
  candidateName: "",
  resumeFile: "",
  professional: "",
  target: "",
  skills: "",
  projectName: "",
  contribution: "",
  technicalPlan: "",
  debugging: "",
  result: ""
}
```

`resumeParsed`、`candidateName`、`resumeFile` 只留在 A 侧；D 只接收 `agentAdapter` 转换后的 `project`。

## 7. Mock 数据

`d/mock_data/` 下提供：
- `project.json`：共享项目。
- `turn_01_main.json`：主问题请求 + 响应。
- `turn_02_followup_1.json`：第一次追问。
- `turn_03_followup_2.json`：第二次追问。
- `feedback_final.json`：结束面试后的 full 复盘。
- `feedback_degraded.json`：ASR/Agent 不可用时的 degraded 复盘（带 `notice`）。

`d/test_agent_flow.py` 会按本契约校验这些文件并模拟 A→D→A 流程。
