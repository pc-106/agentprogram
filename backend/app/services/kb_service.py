"""知识库管理：状态、文档清单、检索测试、重建索引、报告数据目录。"""

from __future__ import annotations

import time
from typing import Any

from ..core import config
from .local_index import LocalSearchIndex, _HAS_JIEBA
from .records import RecordBook

SAMPLE_QUESTIONS = [
    "80㎡ 有宠物，3000 元以内选哪种？",
    "机器人回充失败怎么办？",
    "滤网多久换一次？",
    "拖地后地面有水痕怎么处理？",
    "边刷不转了是哪里坏了？",
    "生成我的使用报告",
]


def _chroma_count(chroma_dir) -> int | None:
    """只读统计真实向量库片段数；库不存在或读取失败时返回 None。"""
    if not chroma_dir.is_dir():
        return None
    try:
        import chromadb

        client = chromadb.PersistentClient(path=str(chroma_dir))
        return int(client.get_collection(config.COLLECTION_NAME).count())
    except Exception:
        return None


class KBService:
    def __init__(self, index: LocalSearchIndex, records: RecordBook) -> None:
        self.index = index
        self.records = records

    # ------------------------------------------------------------------ #
    def status(self) -> dict[str, Any]:
        stats = self.index.stats()
        chroma_dir = config.LEGACY_DIR / str(config.CHROMA_CONF.get("persist_directory") or "chroma_db")
        md5_file = config.LEGACY_DIR / str(config.CHROMA_CONF.get("md5_hex_store") or "md5.text")
        return {
            **stats,
            "engine": "bm25-local" if config.MODE == "demo" else "langchain-chroma",
            "tokenizer": "jieba" if _HAS_JIEBA else "bigram",
            "collection": config.COLLECTION_NAME,
            "embedding_model": config.EMBEDDING_MODEL_NAME,
            "chunk_size": config.CHUNK_SIZE,
            "chunk_overlap": config.CHUNK_OVERLAP,
            "retrieve_k": config.RETRIEVE_K,
            "chroma": {
                "path": str(chroma_dir),
                "exists": chroma_dir.is_dir(),
                "md5_store_exists": md5_file.is_file(),
                "count": _chroma_count(chroma_dir),
            },
            "legacy_dir": str(config.LEGACY_DIR),
        }

    def documents(self) -> list[dict[str, Any]]:
        return self.index.documents()

    def search(self, query: str, k: int = 3) -> dict[str, Any]:
        started = time.perf_counter()
        hits = self.index.search(query, k=k)
        return {
            "query": query,
            "k": k,
            "took_ms": round((time.perf_counter() - started) * 1000, 2),
            "items": [hit.to_dict() for hit in hits],
        }

    def reindex(self) -> dict[str, Any]:
        started = time.perf_counter()
        self.index.build()
        return {
            "took_ms": round((time.perf_counter() - started) * 1000, 2),
            "status": self.status(),
        }

    # ------------------------------------------------------------------ #
    def record_catalog(self) -> dict[str, Any]:
        users = []
        for user_id in self.records.users:
            months = self.records.months_of(user_id)
            latest = months[-1] if months else ""
            record = self.records.get(user_id, latest) if latest else None
            users.append(
                {
                    "user_id": user_id,
                    "months": months,
                    "latest_month": latest,
                    "feature": record.feature if record else "",
                }
            )
        return {
            "users": users,
            "months": self.records.months,
            "total_records": len(self.records.all_records()),
        }
