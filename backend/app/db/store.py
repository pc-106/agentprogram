"""SQLite 会话持久化。

轻量、无外部依赖，单文件数据库位于 ``backend/data/app.db``。
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Iterator

from ..core.config import DB_PATH, ensure_runtime_dirs

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    mode        TEXT NOT NULL DEFAULT 'demo',
    pinned      INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id          TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    meta        TEXT NOT NULL DEFAULT '{}',
    seq         INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id, seq);
CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at DESC);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id() -> str:
    return uuid.uuid4().hex


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    ensure_runtime_dirs()
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)


# --------------------------------------------------------------------------- #
# 会话
# --------------------------------------------------------------------------- #
def list_sessions() -> list[dict[str, Any]]:
    sql = """
        SELECT s.*,
               (SELECT COUNT(*) FROM messages m WHERE m.session_id = s.id) AS message_count,
               (SELECT m.content FROM messages m WHERE m.session_id = s.id
                 ORDER BY m.seq DESC LIMIT 1) AS last_message
        FROM sessions s
        ORDER BY s.pinned DESC, s.updated_at DESC
    """
    with connect() as conn:
        rows = conn.execute(sql).fetchall()
    return [_session_row(row) for row in rows]


def get_session(session_id: str) -> dict[str, Any] | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
    return _session_row(row) if row else None


def create_session(title: str = "新对话", mode: str = "demo") -> dict[str, Any]:
    session_id = new_id()
    stamp = _now()
    with connect() as conn:
        conn.execute(
            "INSERT INTO sessions (id, title, mode, pinned, created_at, updated_at) VALUES (?,?,?,0,?,?)",
            (session_id, title, mode, stamp, stamp),
        )
    session = get_session(session_id)
    assert session is not None
    return session


def update_session(
    session_id: str,
    *,
    title: str | None = None,
    pinned: bool | None = None,
    mode: str | None = None,
    touch: bool = False,
) -> dict[str, Any] | None:
    fields: list[str] = []
    params: list[Any] = []
    if title is not None:
        fields.append("title = ?")
        params.append(title)
    if pinned is not None:
        fields.append("pinned = ?")
        params.append(1 if pinned else 0)
    if mode is not None:
        fields.append("mode = ?")
        params.append(mode)
    if touch or fields:
        fields.append("updated_at = ?")
        params.append(_now())
    if not fields:
        return get_session(session_id)
    params.append(session_id)
    with connect() as conn:
        conn.execute(f"UPDATE sessions SET {', '.join(fields)} WHERE id = ?", params)
    return get_session(session_id)


def delete_session(session_id: str) -> bool:
    with connect() as conn:
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
    return cursor.rowcount > 0


def clear_sessions() -> int:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM messages")
    return cursor.rowcount


# --------------------------------------------------------------------------- #
# 消息
# --------------------------------------------------------------------------- #
def list_messages(session_id: str) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY seq ASC", (session_id,)
        ).fetchall()
    return [_message_row(row) for row in rows]


def add_message(
    session_id: str,
    role: str,
    content: str,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    message_id = new_id()
    stamp = _now()
    with connect() as conn:
        row = conn.execute(
            "SELECT COALESCE(MAX(seq), 0) + 1 AS next FROM messages WHERE session_id = ?",
            (session_id,),
        ).fetchone()
        seq = int(row["next"]) if row else 1
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, meta, seq, created_at)"
            " VALUES (?,?,?,?,?,?,?)",
            (message_id, session_id, role, content, json.dumps(meta or {}, ensure_ascii=False), seq, stamp),
        )
        conn.execute("UPDATE sessions SET updated_at = ? WHERE id = ?", (stamp, session_id))
    return {
        "id": message_id,
        "session_id": session_id,
        "role": role,
        "content": content,
        "meta": meta or {},
        "seq": seq,
        "created_at": stamp,
    }


def delete_message(message_id: str) -> bool:
    with connect() as conn:
        cursor = conn.execute("DELETE FROM messages WHERE id = ?", (message_id,))
    return cursor.rowcount > 0


# --------------------------------------------------------------------------- #
# 统计
# --------------------------------------------------------------------------- #
def stats() -> dict[str, int]:
    with connect() as conn:
        sessions = conn.execute("SELECT COUNT(*) AS c FROM sessions").fetchone()["c"]
        messages = conn.execute("SELECT COUNT(*) AS c FROM messages").fetchone()["c"]
    return {"sessions": int(sessions), "messages": int(messages)}


def _session_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    data["pinned"] = bool(data.get("pinned"))
    data.setdefault("message_count", 0)
    return data


def _message_row(row: sqlite3.Row) -> dict[str, Any]:
    data = dict(row)
    try:
        data["meta"] = json.loads(data.get("meta") or "{}")
    except json.JSONDecodeError:
        data["meta"] = {}
    return data
