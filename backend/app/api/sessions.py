"""会话与消息。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..db import store
from ..runtime import get_runtime
from ..schemas.models import SessionCreate, SessionUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("")
def list_sessions() -> dict:
    return {"sessions": store.list_sessions(), "stats": store.stats()}


@router.post("", status_code=201)
def create_session(payload: SessionCreate | None = None) -> dict:
    title = (payload.title if payload and payload.title else "新对话").strip() or "新对话"
    return store.create_session(title=title, mode=get_runtime().engine.mode)


@router.get("/{session_id}")
def get_session(session_id: str) -> dict:
    session = store.get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"session": session, "messages": store.list_messages(session_id)}


@router.patch("/{session_id}")
def update_session(session_id: str, payload: SessionUpdate) -> dict:
    if store.get_session(session_id) is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    title = payload.title.strip() if isinstance(payload.title, str) else None
    session = store.update_session(session_id, title=title or None, pinned=payload.pinned)
    return {"session": session}


@router.delete("/{session_id}")
def delete_session(session_id: str) -> dict:
    if not store.delete_session(session_id):
        raise HTTPException(status_code=404, detail="会话不存在")
    return {"ok": True, "deleted": session_id}
