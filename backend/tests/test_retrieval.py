"""知识库检索质量：必须能命中对应主题的条目。"""

from __future__ import annotations

import pytest

from app.core.config import LEGACY_DATA_DIR
from app.services.local_index import LocalSearchIndex, split_text, tokenize


@pytest.fixture(scope="module")
def index() -> LocalSearchIndex:
    instance = LocalSearchIndex(LEGACY_DATA_DIR)
    instance.build()
    return instance


def test_index_built(index: LocalSearchIndex) -> None:
    stats = index.stats()
    assert stats["documents"] == 6
    assert stats["chunks"] > 500
    assert stats["indexed_documents"] == 6


def test_pdf_text_available(index: LocalSearchIndex) -> None:
    pdf = [doc for doc in index.documents() if doc["type"] == "pdf"]
    assert pdf and pdf[0]["ok"], "PDF 应能提取出正文"


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        ("滤网多久换一次", "滤网"),
        ("小户型适合哪种扫地机器人", "小户型"),
        ("边刷不转了", "边刷"),
        ("滚刷缠绕头发", "缠绕"),
        ("拖地后地面有水痕", "水痕"),
        ("有宠物的家庭怎么选", "宠物"),
        ("机器人回充失败总是停在半路", "回充"),
        ("电池不耐用", "电池"),
    ],
)
def test_top_hits_cover_topic(index: LocalSearchIndex, query: str, expected: str) -> None:
    hits = index.search(query, k=3)
    assert hits, f"{query} 应有检索结果"
    assert any(expected in hit.chunk.text for hit in hits[:2]), (
        f"{query} 的前两名未包含 {expected}: {[h.chunk.text[:30] for h in hits[:2]]}"
    )


def test_scores_normalized(index: LocalSearchIndex) -> None:
    hits = index.search("噪音大怎么办", k=3)
    assert hits[0].score == 1.0
    assert all(0 < hit.score <= 1.0 for hit in hits)
    assert [hit.score for hit in hits] == sorted((hit.score for hit in hits), reverse=True)


def test_empty_query_returns_nothing(index: LocalSearchIndex) -> None:
    assert index.search("   ") == []


def test_split_text_one_item_per_chunk() -> None:
    text = "# 标题\n\n1. **问题一？**\n- 答案一。\n2. **问题二？**\n- 答案二。\n"
    chunks = split_text(text)
    assert len(chunks) == 2
    assert "问题一" in chunks[0] and "问题二" not in chunks[0]
    assert "问题二" in chunks[1]


def test_tokenizer_keeps_domain_words() -> None:
    tokens = tokenize("滤网多久换一次")
    assert "滤网" in tokens
