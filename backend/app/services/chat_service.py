"""对话编排：会话落库 + 事件流 + 失败兜底。"""

from __future__ import annotations

import time
from typing import Iterator

from ..core.events import (
    CITATIONS,
    DELTA,
    DONE,
    ERROR,
    META,
    NOTICE,
    TOOL_CALL,
    TOOL_RESULT,
    Event,
)
from ..db import store
from .engine import EngineFacade

REPORT_HINT = "（请按报告格式，结合我的使用记录生成一份完整的使用情况报告与保养建议）"


class ChatService:
    def __init__(self, engine: EngineFacade) -> None:
        self.engine = engine

    # ------------------------------------------------------------------ #
    def stream_reply(
        self,
        message: str,
        session_id: str | None,
        intent: str = "chat",
    ) -> Iterator[Event]:
        session = store.get_session(session_id) if session_id else None
        if session is None:
            session = store.create_session(mode=self.engine.mode)
        session_id = session["id"]
        # 首轮对话：无 Key 时需要在回答前告知用户"已切换离线"
        first_turn = not store.list_messages(session_id)

        user_message = store.add_message(session_id, "user", message)
        if session["title"] in {"新对话", ""} or session["title"] is None:
            store.update_session(session_id, title=_make_title(message))

        yield Event(
            META,
            {
                "session_id": session_id,
                "session_title": store.get_session(session_id)["title"],  # type: ignore[index]
                "user_message_id": user_message["id"],
                "mode": self.engine.mode,
                "intent": intent,
            },
        )

        started = time.perf_counter()
        buffer: list[str] = []
        tools: list[dict] = []
        citations: list[dict] = []
        notices: list[dict] = []
        error: dict | None = None

        prompt = message
        if intent == "report" and "报告" not in message:
            prompt = f"{message}{REPORT_HINT}"

        try:
            for event in self.engine.stream(prompt, intent, announce=first_turn):
                if event.name == DELTA:
                    buffer.append(str(event.data.get("text", "")))
                elif event.name == NOTICE:
                    notices.append(event.data)
                elif event.name == TOOL_CALL:
                    tools.append(
                        {
                            "id": event.data.get("id"),
                            "name": event.data.get("name"),
                            "label": event.data.get("label"),
                            "icon": event.data.get("icon"),
                            "args": event.data.get("args") or {},
                            "note": event.data.get("note"),
                            "ok": None,
                            "latency_ms": None,
                            "preview": "",
                        }
                    )
                elif event.name == TOOL_RESULT:
                    _attach_tool_result(tools, event.data)
                elif event.name == CITATIONS:
                    citations = event.data.get("items") or []
                elif event.name == ERROR:
                    error = event.data
                yield event
        except Exception as exc:  # 兜底：绝不让前端只看到断流
            error = {
                "code": "chat_failed",
                "message": "对话生成失败，请稍后重试。",
                "detail": f"{type(exc).__name__}: {exc}",
            }
            yield Event(ERROR, error)

        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        content = "".join(buffer).strip()
        if not content:
            content = "（本次没有生成内容）"

        meta = {
            "mode": self.engine.mode,
            "intent": intent,
            "elapsed_ms": elapsed_ms,
            "tools": tools,
            "citations": citations,
            "notices": notices,
            "error": error,
        }
        assistant = store.add_message(session_id, "assistant", content, meta)

        yield Event(
            DONE,
            {
                "message_id": assistant["id"],
                "session_id": session_id,
                "elapsed_ms": elapsed_ms,
                "tool_calls": len(tools),
                "mode": self.engine.mode,
                "has_error": bool(error),
            },
        )


def _attach_tool_result(tools: list[dict], data: dict) -> None:
    call_id = data.get("id")
    for tool in reversed(tools):
        if tool.get("id") == call_id:
            tool["ok"] = bool(data.get("ok", True))
            tool["latency_ms"] = data.get("latency_ms")
            tool["preview"] = data.get("preview") or ""
            tool["error"] = data.get("error")
            return


def _make_title(message: str) -> str:
    title = " ".join(message.split())
    return title[:24] + ("…" if len(title) > 24 else "")
