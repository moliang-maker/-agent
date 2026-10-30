# 腾讯云 Agent 网页调用信息（核对版）

- 核对日期：2026-10-30
- 用途：回答“Agent 的正式网页调用信息”并区分腾讯云两套 Agent。
- 重要：**灵机 `2736` 不是腾讯 Agent**。灵机没有公开的网页 HTTP/SSE 调用入口；不要把 PID `11814`、Agent `2736` 或产品密钥当腾讯 `AppKey/BotAppKey` 使用。

## 0. 先分清三套东西

| 平台 | 凭据 | 网页调用 | 当前用途 |
|---|---|---|---|
| 灵机一动 `platform.ljyd.cn` | 产品 PID `11814`、Agent `2736`、产品密钥 | 公开文档没有 HTTP/SSE 入口 | 产品/设备绑定，B 的硬件 |
| 腾讯云智能体开发平台（ADP/LKE） | `AppKey`（应用发布后获取） | `POST https://wss.lke.cloud.tencent.com/adp/v2/chat`，SSE | 可选：网页/应用 Agent |
| 腾讯云 CloudBase Agent | 环境 ID、Publishable Key、`botId`、API Key | JS SDK 或 `Authorization: Bearer`，ACP/AG-UI | 可选：另一套 Web Agent |

如果队友说的是 `wss.lke.cloud.tencent.com/v1/qbot/chat/sse`，那是**腾讯 ADP 的旧版 HTTP SSE**；新版是 `/adp/v2/chat`，旧版 2026-12-31 下线。

---

## 1. 腾讯云 ADP：新版 HTTP SSE

### 1.1 地址与请求方式

```text
POST https://wss.lke.cloud.tencent.com/adp/v2/chat
Content-Type: application/json
Accept: text/event-stream
```

旧版（不推荐，2026-12-31 下线）：

```text
POST https://wss.lke.cloud.tencent.com/v1/qbot/chat/sse
```

### 1.2 鉴权

- 没有 `Authorization: Bearer`。
- `AppKey` 放在 **JSON body** 的 `AppKey` 字段。
- `BotBizID` 是应用唯一标识（控制台 URL 的 appid），**新版 HTTP SSE body 不需要它**；不要把它和 `AppKey` 混用。
- `AppKey` 获取：应用管理 → 已发布应用 →「调用」/「服务状态」→ 调用信息窗口复制。
- 应用必须先发布，未发布时「调用」不可用。

### 1.3 可运行 cURL（占位符替换）

```bash
curl --location 'https://wss.lke.cloud.tencent.com/adp/v2/chat' \
  --header 'Content-Type: application/json' \
  --header 'Accept: text/event-stream' \
  --data '{
    "RequestId": "4feb312a-14e9-4161-bfe2-767c43ae0524",
    "ConversationId": "362b3aac-b7eb-4d2a-a154-204f288a4727",
    "AppKey": "<YOUR_APP_KEY>",
    "UserId": "demo-user-001",
    "VisitorId": "demo-user-001",
    "Contents": [
      { "Type": "text", "Text": "请开始面试" }
    ],
    "Incremental": true,
    "Stream": "enable"
  }'
```

不要把真实 `AppKey` 写进 GitHub、前端源码或聊天记录；测试时放本机环境变量。

### 1.4 请求字段

| 字段 | 必填 | 说明 |
|---|---|---|
| `RequestId` | 建议 | 请求 ID，32–64 字符，建议 UUID |
| `ConversationId` | 是 | 会话 ID，32–64 字符，建议 UUID；同一会话复用 |
| `AppKey` | 是 | 应用发布后获取 |
| `UserId` | 是 | 用户 ID；替代即将废弃的 `VisitorId` |
| `VisitorId` | 是（兼容） | 旧字段，文档标注即将废弃；建议和 `UserId` 同值 |
| `Contents` | 是 | 数组：`[{"Type":"text","Text":"..."}]` |
| `Incremental` | 否 | true 时文本走 `text.delta`，必要时有 `text.replace` |
| `Stream` | 否 | `enable` 流式；`disable` 非流式 |
| `StreamingThrottle` | 否 | 每积攒多少字符回包，默认 5，建议 ≤100 |
| `SystemRole` | 否 | 临时覆盖角色指令；为空用应用配置 |
| `WorkflowStatus` | 否 | `enable/disable`，是否走工作流 |

注意：新版是 `Contents` 数组、PascalCase；旧版是 `content` 字符串、snake_case。不要混用。

### 1.5 SSE 响应事件

新版事件顺序示例：

```text
event: request_ack
data: {"Type":"request_ack","RequestAck":{...}}

event: response.created
data: {"Type":"response.created","Response":{...}}

event: response.processing
data: {"Type":"response.processing","Response":{...}}

event: message.added
data: {"Type":"message.added","Message":{...}}

event: content.added
data: {"Type":"content.added","MessageId":"...","ContentIndex":0,"Content":{"Type":"text"}}

event: text.delta
data: {"Type":"text.delta","MessageId":"...","ContentIndex":0,"Text":"您好"}

event: message.done
data: {"Type":"message.done","MessageId":"...","Message":{...}}

event: response.completed
data: {"Type":"response.completed","Response":{...}}

event: done
data: [DONE]
```

提取文本：
- 流式增量：累加 `text.delta` 的 `Text`。
- 最终文本：`message.done.Message.Contents[0].Text` 或 `response.completed.Response.Messages[0].Contents[0].Text`。
- 结束：`data: [DONE]`。

### 1.6 错误

- 普通错误可能返回 `event: error` / `data: {"Type":"error","Error":{"Code":...,"Message":"..."}}`。
- 请求体不合法时也可能直接返回 HTTP 400 JSON，例如 `{"Type":"error","Error":{"Code":999,...}}`。

### 1.7 GitHub Pages 跨域

实测 `OPTIONS https://wss.lke.cloud.tencent.com/adp/v2/chat`，带：

```text
Origin: https://taooow.github.io
Access-Control-Request-Method: POST
Access-Control-Request-Headers: content-type
```

返回：

```text
HTTP/1.1 204 No Content
Access-Control-Allow-Origin: https://taooow.github.io
Access-Control-Allow-Credentials: true
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: ...,Content-Type,Authorization,...
```

结论：
- **技术上允许 GitHub Pages 直接跨域调用**，但浏览器里必须放 `AppKey`，等于公开密钥。
- **不建议**把 `AppKey` 放进 GitHub Pages 静态 JS。
- 建议用后端/Serverless 代理：浏览器 → 你的代理（无密钥）→ 腾讯 SSE（代理注入 AppKey）。GitHub Pages 只放代理地址。
- 如果只做一次性本地演示，可临时直连；演示后立刻在腾讯控制台轮换 `AppKey`。

---

## 2. 腾讯云 CloudBase Agent（另一套，不要和 ADP 混）

CloudBase Agent 不用 `BotAppKey`、不用 `wss.lke.cloud.tencent.com/v1/qbot/chat/sse`。

### 2.1 地址

```text
ACP（cloudbase-agent 模板）：
POST https://{envId}.api.tcloudbasegateway.com/v1/aibot/bots/{agentId}/acp

AG-UI（自建 HTTP Agent）：
POST https://{envId}.api.tcloudbasegateway.com/v1/aibot/bots/{agentId}/send-message
```

### 2.2 鉴权

```text
Authorization: Bearer <YOUR_API_KEY>
Content-Type: application/json
```

- `{envId}`：CloudBase 环境 ID。
- `{agentId}`：CloudBase Agent 的 `botId`。
- API Key 在云开发控制台「设置 → API 密钥」创建。
- Web 端用 `@cloudbase/js-sdk`，初始化需要 `env` 和 `accessKey`（Publishable Key），再 `app.ai().bot.sendMessage({botId,...})`。
- 协议由 Agent 模板决定：端点以 `/acp` 结尾走 ACP；自建 HTTP Agent 走 AG-UI。

### 2.3 cURL（ACP）

```bash
curl 'https://{envId}.api.tcloudbasegateway.com/v1/aibot/bots/{agentId}/acp' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"session/prompt",
    "params":{"prompt":[{"type":"text","text":"你好"}]}
  }'
```

响应是 SSE `data:` 行，正文增量在 `params.update.sessionUpdate === "agent_message_chunk"` 的 `content.text`。

### 2.4 cURL（AG-UI）

```bash
curl 'https://{envId}.api.tcloudbasegateway.com/v1/aibot/bots/{agentId}/send-message' \
  -H 'Authorization: Bearer <YOUR_API_KEY>' \
  -H 'Accept: text/event-stream' \
  -H 'Content-Type: application/json' \
  --data-raw '{
    "threadId":"thread-001",
    "runId":"run-001",
    "messages":[{"id":"msg-1","role":"user","content":"你好"}],
    "tools":[],"context":[],"state":{}
  }'
```

响应事件：`RUN_STARTED`、`TEXT_MESSAGE_START`、`TEXT_MESSAGE_CONTENT`、`TEXT_MESSAGE_END`、`RUN_FINISHED`。

---

## 3. 七个问题的直接回答

1. **生产 HTTP/SSE 地址**
   - 腾讯 ADP：`https://wss.lke.cloud.tencent.com/adp/v2/chat`
   - 旧版：`https://wss.lke.cloud.tencent.com/v1/qbot/chat/sse`（2026-12-31 下线）
   - CloudBase：`https://{envId}.api.tcloudbasegateway.com/v1/aibot/bots/{agentId}/acp` 或 `/send-message`
2. **鉴权**
   - 腾讯 ADP：`AppKey` 放 body，无 Bearer。
   - CloudBase：`Authorization: Bearer <API_KEY>`。
3. **cURL**
   - 见上文 1.3 / 2.3 / 2.4。
4. **请求体字段**
   - 腾讯 ADP：`RequestId`、`ConversationId`、`AppKey`、`UserId`、`VisitorId`、`Contents`、`Incremental`、`Stream`。
   - CloudBase ACP：JSON-RPC `method=session/prompt`、`params.prompt`；AG-UI：`threadId/runId/messages`。
5. **流式事件格式**
   - 腾讯 ADP：`request_ack` → `response.created` → `text.delta` → `message.done` → `response.completed` → `data: [DONE]`。
   - CloudBase ACP：`session/update` + `agent_message_chunk`；AG-UI：`TEXT_MESSAGE_CONTENT.delta`。
6. **GitHub Pages 跨域**
   - 腾讯 ADP 实测允许 `https://taooow.github.io` 的预检；但 `AppKey` 会暴露，不建议静态页直连。
7. **是否建议后端代理**
   - 建议。GitHub Pages 没有服务端，密钥必须放代理/Serverless；前端只拿代理地址。

## 4. 给队友的结论

- 如果要用**腾讯 ADP**：请提供 `AppKey`（私聊）+ 已发布应用；我们按新版 `/adp/v2/chat` 接，旧版 `/v1/qbot/chat/sse` 不要再用。
- 如果要用**CloudBase**：请提供 `envId`、`Publishable Key`、`botId`、协议（ACP/AG-UI）和服务端 API Key；网页用 `@cloudbase/js-sdk`。
- 如果继续用**灵机 2736**：网页没有公开 HTTP/SSE，A 的网页只能走 D 的 `/api/agent`；PID `11814` 只给 B 做设备，不用于腾讯接口。

## 5. 官方来源

- 腾讯云 ADP 新版 HTTP SSE：https://cloud.tencent.cn/document/product/1759/129202
- 腾讯云 ADP 旧版 HTTP SSE：https://cloud.tencent.cn/document/product/1759/105561
- BotBizID / BotAppKey 获取：https://cloud.tencent.cn/document/product/1759/109469
- CloudBase Web 调用：https://docs.cloudbase.net/ai/agent-development/integration/web
- CloudBase cURL：https://docs.cloudbase.net/ai/agent-development/integration/curl
