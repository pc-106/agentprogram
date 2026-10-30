"""全局配置：路径、运行模式、模型参数。

设计要点：
* 原工程 ``ragagent/`` 只被**读取**，不被写入；
* 新的持久化数据（会话数据库）放在 ``backend/data/``；
* 运行模式由 ``DASHSCOPE_API_KEY`` 自动判定，可用 ``AGENT_MODE`` 覆盖。
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml

Mode = Literal["real", "demo"]


# --------------------------------------------------------------------------- #
# .env
# --------------------------------------------------------------------------- #
def _load_dotenv(path: Path) -> None:
    """极简 .env 解析：仅在环境变量缺省时写入，不覆盖已有系统变量。"""
    if not path.is_file():
        return
    try:
        raw_lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return

    for raw in raw_lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


# --------------------------------------------------------------------------- #
# 路径
# --------------------------------------------------------------------------- #
BACKEND_DIR = Path(__file__).resolve().parents[2]          # backend/
REPO_ROOT = BACKEND_DIR.parent                              # 仓库根目录

LEGACY_DIR = Path(os.getenv("LEGACY_DIR") or (REPO_ROOT / "ragagent")).resolve()

# 不要求任何 .env 文件：Key 一律从系统环境变量读取。
# 仅当原工程目录存在 ragagent/.env 时顺带加载（复刻原 config_handler 的 load_dotenv），
# 用于保留你放在那里的 AMAP_API_KEY；文件不存在会直接跳过，不会报错。
_load_dotenv(LEGACY_DIR / ".env")

LEGACY_DATA_DIR = LEGACY_DIR / "data"
RUNTIME_DIR = Path(os.getenv("RUNTIME_DIR") or (BACKEND_DIR / "data"))
DB_PATH = Path(os.getenv("APP_DB") or (RUNTIME_DIR / "app.db"))
FRONTEND_DIST = Path(os.getenv("FRONTEND_DIST") or (REPO_ROOT / "frontend" / "dist"))


def ensure_runtime_dirs() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)


# --------------------------------------------------------------------------- #
# 读取原工程的 yaml 配置（只读）
# --------------------------------------------------------------------------- #
def _read_yaml(relative_path: str) -> dict[str, Any]:
    path = LEGACY_DIR / relative_path
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        return data if isinstance(data, dict) else {}
    except (OSError, yaml.YAMLError):
        return {}


RAG_CONF: dict[str, Any] = _read_yaml("config/rag.yml")
CHROMA_CONF: dict[str, Any] = _read_yaml("config/chroma.yml")
AGENT_CONF: dict[str, Any] = _read_yaml("config/agent.yml")

CHAT_MODEL_NAME: str = str(RAG_CONF.get("chat_model_name") or "qwen3.8-omni-flash")
EMBEDDING_MODEL_NAME: str = str(RAG_CONF.get("embedding_model_name") or "qwen3.7-text-embedding-flash")
COLLECTION_NAME: str = str(CHROMA_CONF.get("collection_name") or "agent")
CHUNK_SIZE: int = int(CHROMA_CONF.get("chunk_size") or 200)
CHUNK_OVERLAP: int = int(CHROMA_CONF.get("chunk_overlap") or 20)
RETRIEVE_K: int = int(CHROMA_CONF.get("k") or 3)


# --------------------------------------------------------------------------- #
# 运行模式
# --------------------------------------------------------------------------- #
HAS_API_KEY: bool = bool((os.getenv("DASHSCOPE_API_KEY") or "").strip())
_raw_mode = (os.getenv("AGENT_MODE") or "auto").strip().lower()
if _raw_mode not in {"auto", "real", "demo"}:
    _raw_mode = "auto"
MODE_REQUESTED: str = _raw_mode

if _raw_mode == "demo":
    MODE: Mode = "demo"
    MODE_NOTE = "已通过 AGENT_MODE=demo 强制使用离线演示模式。"
elif _raw_mode == "real":
    MODE = "real"
    MODE_NOTE = (
        "已通过 AGENT_MODE=real 强制使用真实 Agent 模式。"
        if HAS_API_KEY
        else "已强制真实模式，但未检测到 DASHSCOPE_API_KEY，调用模型会失败。"
    )
else:
    MODE = "real" if HAS_API_KEY else "demo"
    MODE_NOTE = (
        "检测到 DASHSCOPE_API_KEY，使用真实 Agent 模式；调用失败时会提示并自动切换到离线回答。"
        if HAS_API_KEY
        else "未检测到 DASHSCOPE_API_KEY，自动使用离线演示模式（本地检索 + 模板化回答）。"
    )

CORS_ORIGINS: list[str] = [
    item.strip()
    for item in (os.getenv("CORS_ORIGINS") or "http://localhost:5173,http://127.0.0.1:5173").split(",")
    if item.strip()
]

HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8000"))
