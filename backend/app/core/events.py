"""SSE 事件协议。

前端通过 ``fetch`` + ``ReadableStream`` 消费（POST 请求，EventSource 只支持 GET）。

事件序列：

``meta``       一次，会话/模式/消息 id
``status``     0..n，阶段提示（"正在调用工具…"）
``think``      0..n，模型思考/路由说明
``tool_call``  0..n，发起工具调用
``tool_result``0..n，工具返回
``citations``  0..1，知识库引用
``delta``      n..，正文增量
``done``       一次，耗时/统计
``error``      0..1，错误
"""

from __future__ import annotations

import json
from typing import Any, Iterable


class Event:
    """结构化事件：``Event("tool_call", {...})``。"""

    __slots__ = ("name", "data")

    def __init__(self, name: str, data: dict[str, Any] | None = None) -> None:
        self.name = name
        self.data = data or {}

    def to_sse(self) -> str:
        payload = json.dumps(self.data, ensure_ascii=False, default=str)
        return f"event: {self.name}\ndata: {payload}\n\n"

    def __repr__(self) -> str:  # pragma: no cover - 调试用
        return f"Event({self.name!r}, {self.data!r})"


def sse_response_chunks(events: Iterable[Event]) -> Iterable[str]:
    for event in events:
        yield event.to_sse()


META = "meta"
STATUS = "status"
NOTICE = "notice"
THINK = "think"
TOOL_CALL = "tool_call"
TOOL_RESULT = "tool_result"
CITATIONS = "citations"
DELTA = "delta"
DONE = "done"
ERROR = "error"


def tool_meta(name: str) -> dict[str, Any]:
    """工具名 -> 展示元信息（前端也可自行映射，这里作为权威来源）。"""
    from .tools_meta import TOOL_META

    return TOOL_META.get(name, {"label": name, "icon": "wrench", "description": "工具调用"})
