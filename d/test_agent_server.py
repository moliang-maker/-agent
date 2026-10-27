#!/usr/bin/env python3
"""本地启动 Mock Agent 服务并走一遍 HTTP 流程，供 C 接入前自测。

运行：
    python d/test_agent_server.py
"""

from __future__ import annotations

import json
import threading
import urllib.request
from pathlib import Path
from typing import Any

from agent_server import create_server, reset_sessions

ROOT = Path(__file__).resolve().parent
MOCK = ROOT / "mock_data"


def load(name: str) -> dict[str, Any]:
    return json.loads((MOCK / name).read_text(encoding="utf-8"))


def post(base: str, payload: dict[str, Any]) -> dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        base + "/api/agent",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def get_state(base: str, session_id: str) -> dict[str, Any]:
    with urllib.request.urlopen(base + f"/api/agent/state?session_id={session_id}", timeout=5) as resp:
        return json.loads(resp.read().decode("utf-8"))


def require(cond: bool, message: str) -> None:
    if not cond:
        raise AssertionError(message)


def main() -> int:
    reset_sessions()
    server = create_server("127.0.0.1", 0)
    port = server.server_port
    base = f"http://127.0.0.1:{port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        start = load("turn_01_main.json")["request"]
        r1 = post(base, start)
        require(r1["type"] == "question" and r1["question"]["turn_id"] == "q_001", "主问失败")
        require(r1["question"]["is_followup"] is False, "主问 is_followup 应为 false")

        # 幂等：同一 start request_id 重发，必须返回同一结果，不能 409
        r1b = post(base, start)
        require(r1b == r1, "重复 start request_id 未重放同一响应")

        state = get_state(base, start["session_id"])
        require(state["state"] == "interviewing", "state 应为 interviewing")
        require(state["reminder_allowed"] is True, "面试中应允许提醒")

        r2 = post(base, load("turn_02_followup_1.json")["request"])
        require(r2["type"] == "question" and r2["question"]["is_followup"] is True, "第一次追问失败")
        r2b = post(base, load("turn_02_followup_1.json")["request"])
        require(r2b == r2, "重复 answer request_id 未重放同一响应")

        r3 = post(base, load("turn_03_followup_2.json")["request"])
        require(r3["type"] == "question" and r3["question"]["is_followup"] is True, "第二次追问失败")

        r4 = post(base, load("feedback_final.json")["request"])
        require(r4["type"] == "feedback" and r4["feedback"]["mode"] == "full", "full 复盘失败")

        state2 = get_state(base, start["session_id"])
        require(state2["state"] == "reviewing", "复盘后 state 应为 reviewing")
        require(state2["reminder_allowed"] is False, "复盘时不应提醒")

        # 重练：必须清空本轮回答；retry 后不回答直接 end，应 degraded
        retry_req = {
            "contract_version": "1.0",
            "request_id": "req_retry_001",
            "session_id": start["session_id"],
            "action": "retry",
            "state": "reviewing",
        }
        r5 = post(base, retry_req)
        require(r5["question"]["turn_id"] == "q_001", "重练未回到 q_001")
        state3 = get_state(base, start["session_id"])
        require(state3["attempt"] == 2, "重练后 attempt 应为 2")
        require(state3["round_answers"] == 0, "重练后本轮回答应清空")

        end_req = {
            "contract_version": "1.0",
            "request_id": "req_retry_end_001",
            "session_id": start["session_id"],
            "action": "end_interview",
            "state": "interviewing",
        }
        r6 = post(base, end_req)
        require(r6["feedback"]["mode"] == "degraded", "重练未回答就结束应为 degraded")

        print("AGENT SERVER OK")
        print(f"  q_001 -> q_002 -> q_003 -> feedback")
        print(f"  idempotency: start/answer replay OK")
        print(f"  retry: attempt={state3['attempt']} round_answers={state3['round_answers']} end_mode={r6['feedback']['mode']}")
        print(f"  reminder_allowed: interviewing={state['reminder_allowed']} reviewing={state2['reminder_allowed']}")
        return 0
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)


if __name__ == "__main__":
    raise SystemExit(main())
