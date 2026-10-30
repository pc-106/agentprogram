"""API 端到端：健康检查、SSE 对话、会话持久化、知识库。"""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def parse_sse(raw: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    for block in raw.split("\n\n"):
        block = block.strip()
        if not block:
            continue
        lines = block.split("\n")
        name = lines[0].removeprefix("event: ").strip()
        payload = "".join(line.removeprefix("data: ") for line in lines[1:])
        events.append((name, json.loads(payload or "{}")))
    return events


def test_health(client: TestClient) -> None:
    data = client.get("/api/health").json()
    assert data["ok"] is True
    assert data["mode"] in {"demo", "real"}
    assert data["kb"]["documents"] == 6


def test_system_config(client: TestClient) -> None:
    data = client.get("/api/system/config").json()
    assert len(data["tools"]) == 7
    assert "扫地机器人" in data["prompts"]["main"]
    assert data["legacy"]["prepared"] is True
    assert data["legacy"]["notes"], "兼容层应记录修正项"


def test_chat_stream_and_persistence(client: TestClient) -> None:
    response = client.post("/api/chat", json={"message": "滤网多久换一次？"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = parse_sse(response.text)
    names = [name for name, _ in events]
    assert names[0] == "meta"
    assert names[-1] == "done"
    assert {"think", "tool_call", "tool_result", "delta", "citations"} <= set(names)

    answer = "".join(data.get("text", "") for name, data in events if name == "delta")
    assert "滤网" in answer

    session_id = events[0][1]["session_id"]
    detail = client.get(f"/api/sessions/{session_id}").json()
    assert [message["role"] for message in detail["messages"]] == ["user", "assistant"]

    meta = detail["messages"][-1]["meta"]
    assert meta["tools"] and meta["tools"][0]["ok"] is True
    assert meta["citations"]
    assert meta["mode"] == "demo"


def test_report_intent(client: TestClient) -> None:
    response = client.post(
        "/api/chat",
        json={"message": "生成 1002 在 2025-03 的使用报告", "intent": "report"},
    )
    events = parse_sse(response.text)
    answer = "".join(data.get("text", "") for name, data in events if name == "delta")
    assert "# 1002 在 2025-03" in answer
    assert "## 三、保养与使用建议" in answer

    tool_names = [data["name"] for name, data in events if name == "tool_call"]
    assert tool_names == [
        "get_user_id",
        "get_current_month",
        "fill_context_for_report",
        "fetch_external_data",
        "rag_summarize",
    ]


def test_empty_message_rejected(client: TestClient) -> None:
    response = client.post("/api/chat", json={"message": "   "})
    assert response.status_code == 422


def test_session_crud(client: TestClient) -> None:
    created = client.post("/api/sessions", json={"title": "测试会话"}).json()
    session_id = created["id"]
    assert created["title"] == "测试会话"

    renamed = client.patch(f"/api/sessions/{session_id}", json={"title": "改名后"}).json()
    assert renamed["session"]["title"] == "改名后"

    pinned = client.patch(f"/api/sessions/{session_id}", json={"pinned": True}).json()
    assert pinned["session"]["pinned"] is True

    listed = client.get("/api/sessions").json()["sessions"]
    assert any(item["id"] == session_id for item in listed)
    assert listed[0]["id"] == session_id  # 置顶排在最前

    assert client.delete(f"/api/sessions/{session_id}").status_code == 200
    assert client.get(f"/api/sessions/{session_id}").status_code == 404


def test_kb_endpoints(client: TestClient) -> None:
    status = client.get("/api/kb/status").json()
    assert status["documents"] == 6
    assert status["engine"] == "bm25-local"

    docs = client.get("/api/kb/documents").json()["documents"]
    assert len(docs) == 6

    search = client.post("/api/kb/search", json={"query": "边刷不转", "k": 2}).json()
    assert search["items"]
    assert search["took_ms"] >= 0

    reindexed = client.post("/api/kb/reindex").json()
    assert reindexed["status"]["chunks"] > 500

    records = client.get("/api/kb/records").json()
    assert len(records["users"]) == 10
    assert records["total_records"] == 120
