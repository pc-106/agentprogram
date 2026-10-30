"""请求/响应模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    session_id: str | None = Field(default=None, description="为空则自动新建会话")
    message: str = Field(min_length=1, max_length=4000)
    intent: Literal["chat", "report"] = "chat"


class SessionCreate(BaseModel):
    title: str | None = Field(default=None, max_length=80)


class SessionUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=80)
    pinned: bool | None = None


class KBSearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=200)
    k: int = Field(default=3, ge=1, le=10)


class FeedbackRequest(BaseModel):
    message_id: str
    session_id: str
    rating: Literal["up", "down"]


class ApiModel(BaseModel):
    ok: bool = True
    data: Any = None
    message: str | None = None
