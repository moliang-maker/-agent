# Mock 数据

用于 A 端联调与 D 端接口自测，不包含真实简历或个人信息。

- `project.json`：已确认项目（A 传给 D 的 `project`）。
- `turn_01_main.json`：主问题请求/响应。
- `turn_02_followup_1.json`：第一次追问（P01 个人贡献）。
- `turn_03_followup_2.json`：第二次追问（E01 数据）。
- `feedback_final.json`：用户补数据后，D 返回的 full 复盘结果。
- `feedback_degraded.json`：ASR/Agent 不可用时的 degraded 复盘（`notice` 字段供 A 复用渲染）。

所有文件严格按 `d/docs/api-contract.md` 的 `request` / `response` 结构编写；A 可把这些 JSON 当作前端联调夹具。
