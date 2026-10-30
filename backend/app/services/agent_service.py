"""真实 Agent 模式：复用 ``ragagent`` 里的 ReAct Agent 与 7 个工具。

原工程 ``ReAct_Agent`` 只提供 ``execute_stream``（拼接后的纯文本），
新版前端需要「思考 / 工具调用 / 工具结果 / 正文」分开的轨迹，
因此这里直接消费 LangGraph 的 ``stream_mode="messages"`` 事件流，
再转换成统一的 SSE 事件，**不改动原 Agent 代码**。
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Iterator

from ..core.events import CITATIONS, DELTA, THINK, TOOL_CALL, TOOL_RESULT, Event, tool_meta
from ..core.legacy import import_agent_class, prepare_legacy_imports

try:  # demo 模式可以不装 langchain
    from langchain_core.messages import ToolMessage as _ToolMessage
except ImportError:  # pragma: no cover
    _ToolMessage = None  # type: ignore[assignment]

_PENDING = object()

#: 原工程 ``RagSummarizeService.retriever_docs`` 最近一次检索结果（由下面的 hook 写入）
_LAST_RETRIEVAL: dict[str, Any] = {"query": "", "docs": []}


def _install_retrieval_hook() -> None:
    """在不改原代码的前提下，拦截 RAG 工具真正检索到的文档。

    原 ``rag_summarize`` 只返回"总结后的字符串"，检索到的 chunk 不对外暴露。
    这里包一层 ``retriever_docs``，把本次命中的 Document 存到模块级变量，
    供 SSE 的 ``citations`` 事件回传给前端。
    """
    try:
        from rag.rag_service import RagSummarizeService
    except Exception:  # 原工程未安装/导入失败时忽略
        return
    if getattr(RagSummarizeService, "_web_retrieval_hooked", False):
        return

    original = RagSummarizeService.retriever_docs

    def patched(self, query: str):
        docs = original(self, query)
        _LAST_RETRIEVAL["query"] = query
        _LAST_RETRIEVAL["docs"] = list(docs)
        return docs

    RagSummarizeService.retriever_docs = patched  # type: ignore[method-assign]
    RagSummarizeService._web_retrieval_hooked = True  # type: ignore[attr-defined]


def _citations_from_docs(docs: list[Any], limit: int = 5) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, doc in enumerate(docs[:limit], start=1):
        metadata = getattr(doc, "metadata", {}) or {}
        raw_source = str(metadata.get("source") or metadata.get("file_path") or "知识库")
        source = Path(raw_source).name or "知识库"
        text = (getattr(doc, "page_content", "") or "").strip()
        if not text:
            continue
        items.append(
            {
                "id": f"real-{index}",
                "source": source,
                "title": text.splitlines()[0][:40],
                "rank": index,
                "snippet": text[:220],
                "text": text,
            }
        )
    return items


class RealAgentService:
    """把原 ``ReAct_Agent`` 包装成事件流服务。"""

    def __init__(self) -> None:
        prepare_legacy_imports()
        agent_class = import_agent_class()
        self._graph = agent_class().agent
        _install_retrieval_hook()
        self.started_at = time.time()
        self.turns = 0

    def stream(self, message: str, intent: str = "chat") -> Iterator[Event]:
        payload = {"messages": [{"role": "user", "content": message}]}
        mapper = StreamMapper()
        self.turns += 1
        _LAST_RETRIEVAL["query"] = ""
        _LAST_RETRIEVAL["docs"] = []

        # 原工程的 dynamic_prompt 中间件依赖 runtime.context
        stream = self._graph.stream(
            payload,
            stream_mode="messages",
            context={"report": intent == "report"},
        )
        for item in stream:
            for event in mapper.feed(item):
                if event.name == TOOL_RESULT and event.data.get("name") == "rag_summarize":
                    items = _citations_from_docs(_LAST_RETRIEVAL.get("docs") or [])
                    if items:
                        yield Event(CITATIONS, {"items": items})
                yield event
        yield from mapper.flush()


class StreamMapper:
    """LangChain / LangGraph 消息流 -> 前端事件。

    单独抽出来便于用构造的 chunk 做单元测试（无需真实模型）。
    """

    def __init__(self) -> None:
        self.calls: dict[str, dict[str, Any]] = {}
        self.order: list[str] = []
        self.emitted: set[str] = set()
        self.finished: set[str] = set()
        self.tool_count = 0
        self._index_to_id: dict[int, str] = {}
        self._started: dict[str, float] = {}

    # ------------------------------------------------------------------ #
    def feed(self, item: Any) -> Iterator[Event]:
        chunk, _metadata = item if isinstance(item, tuple) and len(item) == 2 else (item, {})
        if chunk is None:
            return

        if _ToolMessage is not None and isinstance(chunk, _ToolMessage):
            yield from self._on_tool_message(chunk)
            return

        self._accumulate(chunk)

        text = _text_of(getattr(chunk, "content", ""))
        if text:
            if getattr(chunk, "tool_call_chunks", None) or getattr(chunk, "tool_calls", None):
                # 模型在调用工具前输出的思考过程
                yield Event(THINK, {"text": text.strip()})
            else:
                yield Event(DELTA, {"text": text})

        yield from self._maybe_emit()

    def flush(self) -> Iterator[Event]:
        for call_id in self.order:
            if call_id in self.emitted or call_id in self.finished:
                continue
            yield from self._emit_call(call_id)

    # ------------------------------------------------------------------ #
    def _on_tool_message(self, chunk: Any) -> Iterator[Event]:
        call_id = str(getattr(chunk, "tool_call_id", "") or "")
        yield from self._emit_call(call_id)

        content = _text_of(getattr(chunk, "content", ""))
        started = self._started.pop(call_id, None)
        latency = round((time.perf_counter() - started) * 1000, 2) if started else None
        name = self.calls.get(call_id, {}).get("name") or "tool"
        meta = tool_meta(name)
        self.finished.add(call_id)
        yield Event(
            TOOL_RESULT,
            {
                "id": call_id,
                "name": name,
                "label": meta["label"],
                "ok": getattr(chunk, "status", "success") != "error",
                "error": None,
                "latency_ms": latency,
                "preview": _preview(content),
            },
        )

    def _accumulate(self, chunk: Any) -> None:
        # 流式 tool_call 片段：{"name","args","id","index"}
        for index, piece in enumerate(getattr(chunk, "tool_call_chunks", None) or []):
            if not isinstance(piece, dict):
                continue

            slot_index = piece.get("index")
            call_id = piece.get("id")
            if call_id:
                if isinstance(slot_index, int):
                    self._index_to_id[slot_index] = call_id
            elif isinstance(slot_index, int):
                call_id = self._index_to_id.get(slot_index)
            if not call_id:
                call_id = self._index_to_id.setdefault(
                    slot_index if isinstance(slot_index, int) else index,
                    f"anon_{slot_index if isinstance(slot_index, int) else index}",
                )

            slot = self.calls.get(call_id)
            if slot is None:
                slot = {"name": "", "args": "", "args_obj": None}
                self.calls[call_id] = slot
                self.order.append(call_id)

            name = piece.get("name")
            if name:
                slot["name"] = name
            args = piece.get("args")
            if args:
                slot["args"] += args if isinstance(args, str) else json.dumps(args, ensure_ascii=False)

        # 非流式 tool_calls（部分模型一次给全）
        for position, call in enumerate(getattr(chunk, "tool_calls", None) or []):
            if not isinstance(call, dict):
                continue
            call_id = str(call.get("id") or f"call_{position}")
            slot = self.calls.setdefault(call_id, {"name": "", "args": "", "args_obj": None})
            if call_id not in self.order:
                self.order.append(call_id)
            slot["name"] = call.get("name") or slot["name"]
            slot["args_obj"] = call.get("args") or slot["args_obj"]

    def _maybe_emit(self) -> Iterator[Event]:
        """参数 JSON 完整时立刻发出 tool_call，让前端先看到"正在调用"再看到结果。"""
        for call_id in self.order:
            slot = self.calls[call_id]
            if call_id in self.emitted or not slot.get("name"):
                continue
            parsed = _parse_args(slot)
            if parsed is _PENDING:
                continue
            slot["args_obj"] = parsed
            yield from self._emit_call(call_id)

    def _emit_call(self, call_id: str) -> Iterator[Event]:
        if not call_id or call_id in self.emitted:
            return
        slot = self.calls.get(call_id)
        if not slot or not slot.get("name"):
            return

        name = slot["name"]
        meta = tool_meta(name)
        args = slot.get("args_obj")
        if not isinstance(args, dict):
            parsed = _parse_args(slot)
            args = parsed if parsed is not _PENDING else {}

        self.emitted.add(call_id)
        self.tool_count += 1
        self._started[call_id] = time.perf_counter()
        yield Event(
            TOOL_CALL,
            {
                "id": call_id,
                "name": name,
                "label": meta["label"],
                "icon": meta["icon"],
                "args": args,
                "note": None,
            },
        )


def _parse_args(slot: dict[str, Any]) -> Any:
    args_obj = slot.get("args_obj")
    if isinstance(args_obj, dict) and args_obj:
        return args_obj
    raw = (slot.get("args") or "").strip()
    if not raw:
        return _PENDING
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return _PENDING
    return parsed if isinstance(parsed, dict) else _PENDING


def _text_of(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for block in content:
            if isinstance(block, str):
                parts.append(block)
            elif isinstance(block, dict) and block.get("type") in {"text", "text_delta"}:
                parts.append(str(block.get("text") or ""))
        return "".join(parts)
    return ""


def _preview(text: str, width: int = 240) -> str:
    flat = " ".join(str(text or "").split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"
