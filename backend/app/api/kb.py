"""知识库与报告数据。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..runtime import get_runtime
from ..schemas.models import KBSearchRequest

router = APIRouter(prefix="/kb", tags=["knowledge-base"])


@router.get("/status")
def kb_status() -> dict:
    return get_runtime().kb.status()


@router.get("/documents")
def kb_documents() -> dict:
    runtime = get_runtime()
    return {"documents": runtime.kb.documents(), "status": runtime.kb.status()}


@router.post("/search")
def kb_search(payload: KBSearchRequest) -> dict:
    query = (payload.query or "").strip()
    if not query:
        raise HTTPException(status_code=422, detail="检索词不能为空")
    return get_runtime().kb.search(query, k=payload.k)


@router.post("/reindex")
def kb_reindex() -> dict:
    return get_runtime().kb.reindex()


@router.get("/records")
def kb_records() -> dict:
    return get_runtime().kb.record_catalog()
