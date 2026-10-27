#!/usr/bin/env python3
"""D 的本地 Mock Agent 服务，供 C（以及 A）联调。

- 纯标准库，不调用真实大模型。
- 实现 POST /api/agent 和 GET /api/agent/state。
- 用 d/mock_data 的固定响应，保证与 d/docs/api-contract.md 一致。
- 真实 Agent 尚未接入；这里只验证接口、状态和 C 的提醒时机。

运行：
    python d/agent_server.py --host 127.0.0.1 --port 8000
"""

from __future__ import annotations

import argparse
import copy
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent
MOCK = ROOT / "mock_data"


def load(name: str) -> dict[str, Any]:
    return json.loads((MOCK / name).read_text(encoding="utf-8"))


TURN_MAIN = load("turn_01_main.json")
TURN_FOLLOWUP_1 = load("turn_02_followup_1.json")
TURN_FOLLOWUP_2 = load("turn_03_followup_2.json")
FEEDBACK_FULL = load("feedback_final.json")
FEEDBACK_DEGRADED = load("feedback_degraded.json")

SESSIONS: dict[str, dict[str, Any]] = {}
LOCK = threading.Lock()


def reset_sessions() -> None:
    with LOCK:
        SESSIONS.clear()


def _base_response(req: dict[str, Any], state: str, rtype: str) -> dict[str, Any]:
    return {
        "contract_version": "1.0",
        "request_id": req.get("request_id", ""),
        "session_id": req.get("session_id", ""),
        "state": state,
        "type": rtype,
        "question": None,
        "feedback": None,
        "error": None,
        "meta": {"turn_index": 0, "max_turns": 6, "elapsed_seconds": 0},
    }


def error(req: dict[str, Any], code: str, message: str, state: str = "error") -> dict[str, Any]:
    out = _base_response(req, state, "error")
    out["error"] = {"code": code, "message": message, "recoverable": code in ("E_STATE_CONFLICT", "E_TIMEOUT", "E_ASR_EMPTY")}
    return out


def _question_from(template: dict[str, Any], req: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(template)
    out["request_id"] = req["request_id"]
    out["session_id"] = req["session_id"]
    out["meta"]["turn_index"] = session["turn"]
    session["last_question_id"] = out["question"]["turn_id"]
    return out


def _feedback_from(template: dict[str, Any], req: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(template)
    out["request_id"] = req["request_id"]
    out["session_id"] = req["session_id"]
    out["meta"]["turn_index"] = min(max(1, session["turn"]), 3)
    return out


def _valid_project(project: dict[str, Any] | None) -> bool:
    return isinstance(project, dict) and all(
        isinstance(project.get(k), str) and project[k].strip() for k in ("name", "description", "role")
    )


def handle(req: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    sid = req.get("session_id")
    action = req.get("action")
    if not sid or not isinstance(sid, str):
        return 400, error(req, "E_BAD_REQUEST", "session_id 缺失")
    if req.get("contract_version") != "1.0":
        return 400, error(req, "E_BAD_REQUEST", "contract_version 必须是 1.0")

    with LOCK:
        session = SESSIONS.get(sid)

        if action == "start_interview":
            if not _valid_project(req.get("project")):
                return 400, error(req, "E_PROJECT_INCOMPLETE", "project.name/description/role 必填", "project_selected")
            if session and session.get("state") == "interviewing":
                return 409, error(req, "E_STATE_CONFLICT", "会话已开始", "interviewing")
            session = {
                "session_id": sid,
                "state": "interviewing",
                "turn": 1,
                "last_question_id": "q_001",
                "answers": [],
            }
            SESSIONS[sid] = session
            return 200, _question_from(TURN_MAIN["response"], req, session)

        if not session:
            return 404, error(req, "E_STATE_CONFLICT", "session 不存在，先 start_interview", "error")

        if action == "submit_answer":
            if session["state"] != "interviewing":
                return 409, error(req, "E_STATE_CONFLICT", "当前不在面试中", session["state"])
            answer = req.get("answer") or {}
            if answer.get("turn_id") != session.get("last_question_id"):
                return 409, error(req, "E_STATE_CONFLICT", "answer.turn_id 不是上一问", session["state"])
            if not isinstance(answer.get("text"), str) or not answer["text"].strip():
                return 400, error(req, "E_ASR_EMPTY", "回答为空", session["state"])

            session["answers"].append(answer["text"])
            session["turn"] += 1
            if session["turn"] == 2:
                return 200, _question_from(TURN_FOLLOWUP_1["response"], req, session)
            if session["turn"] == 3:
                return 200, _question_from(TURN_FOLLOWUP_2["response"], req, session)
            session["state"] = "reviewing"
            return 200, _feedback_from(FEEDBACK_FULL["response"], req, session)

        if action == "end_interview":
            session["state"] = "reviewing"
            template = FEEDBACK_FULL["response"] if len(session["answers"]) >= 3 else FEEDBACK_DEGRADED["response"]
            return 200, _feedback_from(template, req, session)

        if action == "retry":
            session["state"] = "interviewing"
            session["turn"] = 1
            session["last_question_id"] = "q_001"
            return 200, _question_from(TURN_MAIN["response"], req, session)

        if action == "complete_session":
            session["state"] = "completed"
            out = _feedback_from(FEEDBACK_DEGRADED["response"], req, session)
            out["state"] = "completed"
            out["feedback"] = {
                "mode": "degraded",
                "summary": "会话已结束。",
                "items": [],
                "strengths": [],
                "retry_plan": None,
                "next_action": "可以关闭页面。",
                "quotes_verified": False,
                "notice": {
                    "quote": "会话已结束",
                    "issue": "用户完成本次练习",
                    "suggestion": "关闭页面或开始新一轮",
                    "severity": "info",
                },
            }
            return 200, out

        return 400, error(req, "E_UNSUPPORTED", f"未知 action: {action}", session["state"])


def state_payload(session_id: str) -> tuple[int, dict[str, Any]]:
    with LOCK:
        session = SESSIONS.get(session_id)
    if not session:
        return 404, {"error": "E_STATE_CONFLICT", "message": "session 不存在"}
    allowed = session["state"] == "interviewing"
    return 200, {
        "session_id": session_id,
        "state": session["state"],
        "turn_index": session["turn"],
        "last_question_id": session.get("last_question_id"),
        "reminder_allowed": allowed,
        "reason": "interviewing" if allowed else f"state={session['state']}",
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "D-AgentMock/1.0"

    def log_message(self, fmt: str, *args: Any) -> None:
        # 保持 C 的串口/终端输出干净；需要调试时再打开
        return

    def _send_json(self, code: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {"ok": True, "service": "d-agent-mock"})
            return
        if parsed.path == "/api/agent/state":
            sid = (parse_qs(parsed.query).get("session_id") or [""])[0]
            code, payload = state_payload(sid)
            self._send_json(code, payload)
            return
        self._send_json(404, {"error": "E_UNSUPPORTED", "message": "unknown path"})

    def do_POST(self) -> None:  # noqa: N802
        if urlparse(self.path).path != "/api/agent":
            self._send_json(404, {"error": "E_UNSUPPORTED", "message": "unknown path"})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            req = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        except (ValueError, UnicodeDecodeError):
            self._send_json(400, error({}, "E_BAD_REQUEST", "请求不是合法 JSON"))
            return
        code, payload = handle(req)
        self._send_json(code, payload)


def create_server(host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    return ThreadingHTTPServer((host, port), Handler)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    server = create_server(args.host, args.port)
    print(f"D mock agent: http://{args.host}:{args.port}")
    print("POST /api/agent | GET /api/agent/state?session_id=... | GET /health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
