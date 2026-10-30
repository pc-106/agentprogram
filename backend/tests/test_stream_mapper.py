"""真实模式的事件映射（用构造的 LangChain 消息验证，无需 API Key）。"""

from __future__ import annotations

from langchain_core.messages import AIMessageChunk, ToolMessage

from app.services.agent_service import StreamMapper


def _names(events) -> list[str]:
    return [event.name for event in events]


def test_text_chunks_become_deltas() -> None:
    mapper = StreamMapper()
    events = list(mapper.feed((AIMessageChunk(content="你好"), {})))
    assert _names(events) == ["delta"]
    assert events[0].data["text"] == "你好"


def test_tool_call_streaming_then_result() -> None:
    mapper = StreamMapper()

    # 1) 模型先流式给出工具名和参数片段
    first = list(
        mapper.feed(
            (
                AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {"name": "rag_summarize", "args": "", "id": "call_1", "index": 0}
                    ],
                ),
                {},
            )
        )
    )
    assert first == [], "参数不完整时不应提前发出 tool_call"

    second = list(
        mapper.feed(
            (
                AIMessageChunk(
                    content="",
                    tool_call_chunks=[{"name": None, "args": '{"query":', "id": None, "index": 0}],
                ),
                {},
            )
        )
    )
    assert second == []

    third = list(
        mapper.feed(
            (
                AIMessageChunk(
                    content="",
                    tool_call_chunks=[
                        {"name": None, "args": '"滤网多久换"}', "id": None, "index": 0}
                    ],
                ),
                {},
            )
        )
    )
    assert _names(third) == ["tool_call"]
    assert third[0].data["args"] == {"query": "滤网多久换"}

    # 2) 工具返回
    result = list(
        mapper.feed(
            (
                ToolMessage(content="HEPA 滤网 3-6 个月更换", tool_call_id="call_1"),
                {},
            )
        )
    )
    assert _names(result) == ["tool_result"]
    assert result[0].data["ok"] is True
    assert "HEPA" in result[0].data["preview"]
    assert mapper.tool_count == 1


def test_thinking_before_tool_is_marked_as_think() -> None:
    mapper = StreamMapper()
    events = list(
        mapper.feed(
            (
                AIMessageChunk(
                    content="需要先检索知识库",
                    tool_call_chunks=[
                        {"name": "rag_summarize", "args": "{}", "id": "c9", "index": 0}
                    ],
                ),
                {},
            )
        )
    )
    names = _names(events)
    assert names[0] == "think"
    assert events[0].data["text"] == "需要先检索知识库"
    assert "tool_call" in names


def test_flush_emits_pending_calls() -> None:
    mapper = StreamMapper()
    list(
        mapper.feed(
            (
                AIMessageChunk(
                    content="",
                    tool_call_chunks=[{"name": "get_weather", "args": "", "id": "c2", "index": 0}],
                ),
                {},
            )
        )
    )
    flushed = list(mapper.flush())
    assert _names(flushed) == ["tool_call"]
    assert flushed[0].data["name"] == "get_weather"
