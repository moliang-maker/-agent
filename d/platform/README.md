# D · 灵机平台配置

平台：https://platform.ljyd.cn/workSpace

## 文件

| 文件 | 用途 |
|---|---|
| `ljyd-agent-profile.md` | 平台字段怎么填、创建步骤、与 D 接口的关系 |
| `ljyd-role-definition.txt` | 直接粘贴到平台“角色定义”的纯文本 |
| `ljyd-test-cases.md` | 平台调试预览用的 6 条语料和通过标准 |
| `ljyd-network-guide-1080.png` | 平台“配网图片”上传用，1080×1080 PNG |
| `ljyd-network-instructions.txt` | 平台“配网说明”粘贴用，80 字 |

## 关键结论

- 平台是 **UI 配置的语音 Agent**，公开文档没有自定义 HTTP Agent/JSON 输出入口。
- 平台侧走原生 Agent：角色定义 + 模型 + 开场白 + 记忆 + ASR/TTS。
- D 的 `POST /api/agent` 继续服务 A 的网页和 C 的提醒联调，不直接挂进平台。
- 两条链路共用同一套人设和追问规则，但输出形态不同：平台说人话，D 返回 JSON。

## 使用顺序

1. 先读 `ljyd-agent-profile.md`。
2. 登录平台，按字段表创建智能体。
3. 角色定义粘贴 `ljyd-role-definition.txt`。
4. 调试预览用 `ljyd-test-cases.md`。
5. 保存草稿 → 发布版本 → 创建产品时绑定。
6. 设备侧由 B 按平台 PID/SDK 流程接入。
