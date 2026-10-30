"""对话接口：SSE 流式返回。"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

from ..runtime import get_runtime
from ..schemas.models import ChatRequest

router = APIRouter(tags=["chat"])

SSE_HEADERS = {
    "Cache-Control": "no-cache, no-transform",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


@router.post("/chat")
def chat(payload: ChatRequest) -> StreamingResponse:
    message = (payload.message or "").strip()
    if not message:
        raise HTTPException(status_code=422, detail="问题不能为空")

    runtime = get_runtime()
    events = runtime.chat.stream_reply(
        message=message,
        session_id=payload.session_id,
        intent=payload.intent,
    )
    return StreamingResponse(
        (event.to_sse() for event in events),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )
