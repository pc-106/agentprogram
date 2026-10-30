"""真实模式：把 RAG 命中的 Document 转成前端 citations。"""

from __future__ import annotations

from types import SimpleNamespace

from app.services.agent_service import _citations_from_docs


def test_citations_from_documents() -> None:
    docs = [
        SimpleNamespace(
            page_content="HEPA 滤网建议 3-6 个月更换一次\n每周用软毛刷清理表面灰尘。",
            metadata={"source": r"D:\webaicode\agentprogram\ragagent\data\维护保养.txt"},
        ),
        SimpleNamespace(
            page_content="拖地后地面有水痕时调小出水量。",
            metadata={"source": r"D:\webaicode\agentprogram\ragagent\data\故障排除.txt"},
        ),
    ]

    items = _citations_from_docs(docs)

    assert [item["source"] for item in items] == ["维护保养.txt", "故障排除.txt"]
    assert items[0]["rank"] == 1
    assert "滤网" in items[0]["snippet"]
    assert "HEPA" in items[0]["title"]
    assert items[1]["snippet"].startswith("拖地后")


def test_citations_skip_empty_documents() -> None:
    docs = [
        SimpleNamespace(page_content="   ", metadata={"source": "a.txt"}),
        SimpleNamespace(page_content="有内容", metadata={}),
    ]
    items = _citations_from_docs(docs)
    assert len(items) == 1
    assert items[0]["source"] == "知识库"
