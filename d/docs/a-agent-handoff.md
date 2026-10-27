# 给 A 的 GPT-6.1 Sol 工作说明（D↔A）

> 背景：A 使用 **GPT-6.1 Sol** 作为编码/联调工作模型。本文把 D 的接口整理成“模型可直接执行”的交接说明；wire format 以 `d/docs/api-contract.md` 和 `d/schemas/*.json` 为准。
>
> A 已确认：`POST /api/agent`、原生 `fetch`、A 侧 `agentAdapter`、`session_id=crypto.randomUUID()`、10 秒超时、错误 Toast 2200ms、复盘按 `quote/issue/suggestion/severity` 渲染、需要 degraded mock。

## 1. 直接粘贴给 A 的模型

```text
你在「难开口陪练」仓库的 a/ 目录实现网页端。只改 a/，不要改 d/。

先读：
- d/docs/api-contract.md
- d/schemas/agent_request.schema.json
- d/schemas/agent_response.schema.json
- d/mock_data/README.md 和 d/mock_data/*.json

A 已确认：
- Agent 端点：POST /api/agent；简历解析仍是 POST /api/resume/parse（A 自己的接口）。
- 请求用原生 fetch，不引入 axios。
- session_id 在新建练习时用 crypto.randomUUID() 生成，字段名固定 session_id。
- 全局状态至少保留 session_id、resumeParsed、candidateName、practiceProject。
- A 提供 agentAdapter.js，把 practiceProject 映射成 D 的 project；不要直接把 practiceProject 塞给 D。
- 请求超时 10 秒，用 AbortController；普通错误 Toast 2200ms；超时文案“Agent 请求超时，请稍后重试”。
- 复盘按 quote/issue/suggestion/severity 渲染；degraded 用 feedback.notice 复用同一套字段。

任务：
1. 定义 AgentRequest / AgentResponse 类型，字段与 d/schemas/*.json 一致。
2. 实现 POST /api/agent（路径固定；后端未就绪时用 d/mock_data 的 JSON 做 mock）。
3. 状态只用 waiting_resume、project_selected、interviewing、reviewing、completed、error。
4. start_interview 传 agentAdapter 生成的 project（name/description/role 必填）。
5. submit_answer 回传上一问的 question.turn_id；retry 传 retry.question_id；end_interview 后展示 feedback；complete_session 结束。
6. 收到 type=question：显示 question.text，保存 turn_id，用 is_followup 显示“追问/主问”。
7. 收到 type=feedback：full 渲染 items[].quote/issue/suggestion/severity；degraded 渲染 feedback.notice（quote/issue/suggestion/severity=info），不显示问题列表。
8. 用 d/mock_data 的 4 个回合 + degraded 复盘做前端夹具。

不要做：
- 不要新增视觉/姿态字段；第一版不消费 C 的数据。
- 不要做录用预测、性格/情绪判断、打分。
- 不要改写 feedback.items[].quote 去“润色”。
- 不要把“参与/协助”显示成“主导/独立负责”。

验收：
- start → 回答 → 追问 1 → 追问 2 → 补数据 → full feedback。
- degraded mock 走通 notice 渲染。
- 状态流转与 d/docs/api-contract.md 第 1 节一致。
```

## 2. D 已提供什么

| 文件 | 用途 |
|---|---|
| `d/docs/api-contract.md` | 人读契约：状态、请求/响应、字段、A 已确认项 |
| `d/schemas/agent_request.schema.json` | 机器可读请求 schema（JSON Schema draft-07） |
| `d/schemas/agent_response.schema.json` | 机器可读响应 schema |
| `d/mock_data/project.json` | 已确认项目 |
| `d/mock_data/turn_01_main.json` | 主问题请求/响应 |
| `d/mock_data/turn_02_followup_1.json` | 第 1 次追问 |
| `d/mock_data/turn_03_followup_2.json` | 第 2 次追问 |
| `d/mock_data/feedback_final.json` | full 复盘 |
| `d/mock_data/feedback_degraded.json` | degraded 复盘（notice） |
| `d/test_agent_flow.py` | D 侧契约自测（不调用模型） |

## 3. A 的状态与适配层

A 侧建议状态结构：

```js
const practiceProject = {
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
};
```

`agentAdapter.js` 参考实现（A 可改字段名，但输出必须是 D 的 `project`）：

```js
export function toAgentProject(p = {}) {
  const description = [
    p.professional,
    p.target,
    p.technicalPlan,
    p.debugging,
    p.result,
  ]
    .filter(Boolean)
    .join("；");

  return {
    name: (p.projectName || "").trim() || "未命名项目",
    description: description || p.contribution || "嵌入式项目",
    role: (p.target || p.professional || "嵌入式开发").trim(),
    tech_stack: String(p.skills || "")
      .split(/[，,、/]/)
      .map((s) => s.trim())
      .filter(Boolean),
    responsibilities: p.contribution ? [p.contribution] : [],
    metrics: [],
    resume_evidence: p.contribution || "",
  };
}
```

说明：
- `resumeParsed`、`candidateName`、`resumeFile` 只留在 A 侧，不进入 D 请求。
- D 不解析 PDF；`POST /api/resume/parse` 仍是 A 的接口。
- `description` 是“用户确认过的项目描述”，不要写模型编造的内容。

## 4. 调用与超时

```js
export async function callAgent(req, { timeoutMs = 10000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch("/api/agent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`agent http ${res.status}`);
    return await res.json();
  } catch (err) {
    if (err.name === "AbortError") {
      throw new Error("Agent 请求超时，请稍后重试");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}
```

- 普通错误 Toast：2200ms。
- 超时：10 秒；文案“Agent 请求超时，请稍后重试”。
- `error.recoverable=true` 时用同一个 `request_id` 重试一次；仍失败再提示用户。

## 5. 复盘渲染

full：

```js
feedback.items.map((it) => ({
  quote: it.quote,
  issue: it.issue,
  suggestion: it.suggestion,
  severity: it.severity, // P0/P1/P2
}));
```

degraded：

```js
feedback.notice && {
  quote: feedback.notice.quote,
  issue: feedback.notice.issue,
  suggestion: feedback.notice.suggestion,
  severity: feedback.notice.severity, // info
};
```

- `items[].quote` 是回答原文子串，直接展示，不改写。
- `notice.quote` 是系统提示文案，**不是用户原话**；不要加引号声称“用户说”。
- `mode=degraded` 不显示问题列表/亮点，只显示 notice + next_action。

## 6. 不需要 A 确认的部分（D 已定）

- `description` 怎么拼：A 的 adapter 可自由拼；D 只要求非空、是用户确认过的内容。
- `session_id` 格式：任意不透明字符串；`crypto.randomUUID()` 带连字符也可以。
- `severity` 颜色/标签：D 只定义 `P0/P1/P2/info`；A 自己映射。
- `E_TIMEOUT` / `E_ASR_EMPTY` mock：D 可按需补，不阻塞 A。
- 全局状态库和 Toast 组件：A 内部实现，D 不依赖。

**真正需要 A 在联调时确认的只有 2 条：**

- [ ] A 能否在 `submit_answer` 回传上一问的 `question.turn_id`。
- [ ] A 的复盘组件能否渲染 degraded 的 `feedback.notice`（复用 `quote/issue/suggestion/severity`）。
- [ ] 复盘页组件是否用 `severity` 直接映射颜色/标签（P0/P1/P2/info）。
