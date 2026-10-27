# C 接入 D Agent（本地 Mock 服务）

C 不需要等真实大模型：D 已提供一个纯标准库的本地 Mock Agent，按 `d/docs/api-contract.md` 返回结构，C 可以先把视觉预览/演示工具接上，验证“什么时候可以提醒、什么时候必须闭嘴”。

## 1. 启动

```bash
python d/agent_server.py --host 127.0.0.1 --port 8000
```

- 只绑定本机；C 的 `c/tools/cvision/preview_server.py` 用 8765，不冲突。
- 无第三方依赖，Python 3.10+ 即可。
- 这是 Mock：固定 q_001 → q_002 → q_003 → feedback，不是真实 LLM 出题。

## 2. C 会用到两个端点

| 方法 | 路径 | 用途 |
|---|---|---|
| `POST` | `/api/agent` | 开始面试、提交回答、结束面试（与 A 同一契约） |
| `GET` | `/api/agent/state?session_id=...` | C 专用状态查询：当前是否允许视觉提醒 |
| `GET` | `/health` | 健康检查 |

## 3. 提醒仲裁（C 最需要的）

C 的视觉提醒/灯光/震动在触发前，先查：

```http
GET /api/agent/state?session_id=<session_id>
```

返回：

```json
{
  "session_id": "3f2a7c1e-9b4d-4c6a-8e21-7d5f0a9b2c34",
  "state": "interviewing",
  "turn_index": 2,
  "last_question_id": "q_002",
  "reminder_allowed": true,
  "reason": "interviewing"
}
```

规则：
- `reminder_allowed=true` 仅在 `state=interviewing`。
- `reviewing`、`completed`、`error`、session 不存在 → `false`。
- `state` 缺失/请求失败 → C 按 `false` 处理（安全默认：不提醒）。
- C 只做**视觉/灯光/震动**提醒，不要用语音打断；D 不读取 C 的姿态数据，也不判断“紧张/情绪”。
- 建议 C 以 300–500ms 轮询一次，不要每帧请求。

## 4. C 的接入流程

```text
C 工具启动
  → POST /api/agent (start_interview) 拿 q_001
  → 用户回答（C 的演示可用文本输入；正式由 B 的 ASR）
  → POST /api/agent (submit_answer)
  → 拿 q_002 / q_003 / feedback
  → 每次要提醒前 GET /api/agent/state
  → feedback 后停止所有提醒
```

C 只传文本回答；**不要**把关键点、肩线、姿态、摄像头帧塞进 Agent 请求。视觉数据留在 C，D 第一版不消费。

## 5. 最小示例（stdlib）

```python
import json
import urllib.request

BASE = "http://127.0.0.1:8000"

def post(payload):
    req = urllib.request.Request(
        BASE + "/api/agent",
        data=json.dumps(payload, ensure_ascii=False).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read())

start = post({
    "contract_version": "1.0",
    "request_id": "req_c_001",
    "session_id": "c-demo-001",
    "action": "start_interview",
    "state": "project_selected",
    "project": {
        "name": "基于STM32的云台控制系统",
        "description": "二轴云台，负责电机控制与CAN通信。",
        "role": "嵌入式软件"
    }
})
print(start["question"]["text"], start["question"]["is_followup"])
```

## 6. curl 示例

```bash
curl -s http://127.0.0.1:8000/health

curl -s "http://127.0.0.1:8000/api/agent/state?session_id=c-demo-001"

curl -s -X POST http://127.0.0.1:8000/api/agent \
  -H "Content-Type: application/json" \
  -d '{"contract_version":"1.0","request_id":"req_c_002","session_id":"c-demo-001","action":"submit_answer","state":"interviewing","answer":{"turn_id":"q_001","text":"我们团队做了云台，效果挺好的。"}}'
```

## 7. Mock 行为与边界

- `start_interview` → `q_001` 主问。
- 第 1 次回答 → `q_002` 追问（ownership）。
- 第 2 次回答 → `q_003` 追问（data）。
- 第 3 次回答 → `feedback` full。
- `end_interview` → 回答不足 3 条时返回 degraded + `notice`。
- `retry` → 回到 `q_001`。
- `complete_session` → `state=completed`。

Mock 的文本是固定的，C **只依赖字段和状态**，不要依赖具体问题内容；真实 Agent 会替换这些文本，契约不变。

## 8. 与 A/B 的边界

- A 也调 `POST /api/agent`，但 A 不需要 `/api/agent/state`；这是 C 的提醒侧信道。
- 如果 C 的提醒运行在设备固件而不是电脑工具上，需要 B 决定由谁发起 HTTP/串口桥接；不要让 C 直接改 B 的引脚或启动逻辑。
- 第一版只验证“视觉提醒不打断复盘/结束”；姿态准确率、真人标定和提醒阈值仍由 C 的 `c/README.md` 与真实验收决定。

## 9. 排障

| 现象 | 检查 |
|---|---|
| 连接失败 | 服务是否启动；端口 8000 是否被占；host 是否 127.0.0.1 |
| 404 session | 先 `start_interview`，并复用同一个 `session_id` |
| 409 `E_STATE_CONFLICT` | `answer.turn_id` 是否是上一问的 `last_question_id` |
| `reminder_allowed=false` | 当前是 `reviewing/completed/error`，应停止提醒 |
| 返回内容固定 | 这是 Mock，不是真实模型；接真实 Agent 后文本会变，字段不变 |
