"""系统信息：健康检查、配置、工具清单。"""

from __future__ import annotations

from fastapi import APIRouter

from .. import __version__
from ..core import config
from ..core.legacy import legacy_report, prepare_legacy_imports, prompt_preview
from ..core.tools_meta import TOOL_META, TOOL_ORDER
from ..db import store
from ..runtime import get_runtime
from ..services.kb_service import SAMPLE_QUESTIONS

router = APIRouter(tags=["system"])


@router.get("/health")
def health() -> dict:
    runtime = get_runtime()
    stats = runtime.index.stats()
    return {
        "ok": True,
        "version": __version__,
        "mode": runtime.engine.mode,
        "fallback": runtime.engine.fallback,
        "uptime_seconds": runtime.uptime_seconds,
        "sessions": store.stats(),
        "kb": {
            "documents": stats["documents"],
            "chunks": stats["chunks"],
            "built_at": stats["built_at"],
        },
    }


@router.get("/system/config")
def system_config() -> dict:
    runtime = get_runtime()
    # 幂等：仅注册 sys.path / 模块别名，不会构造模型
    prepare_legacy_imports()
    return {
        "version": __version__,
        "mode": runtime.engine.describe(),
        "models": {
            "chat": config.CHAT_MODEL_NAME,
            "embedding": config.EMBEDDING_MODEL_NAME,
            "collection": config.COLLECTION_NAME,
        },
        "retrieval": {
            "chunk_size": config.CHUNK_SIZE,
            "chunk_overlap": config.CHUNK_OVERLAP,
            "top_k": config.RETRIEVE_K,
        },
        "paths": {
            "legacy": str(config.LEGACY_DIR),
            "data": str(config.LEGACY_DATA_DIR),
            "database": str(config.DB_PATH),
            "frontend_dist": str(config.FRONTEND_DIST),
        },
        "legacy": legacy_report(),
        "tools": TOOL_META,
        "tool_order": TOOL_ORDER,
        "prompts": {
            "main": prompt_preview("main"),
            "rag": prompt_preview("rag"),
            "report": prompt_preview("report"),
        },
        "samples": SAMPLE_QUESTIONS,
        "stats": {**store.stats(), "kb": runtime.index.stats()},
    }


@router.get("/tools")
def tools() -> dict:
    return {"tools": TOOL_META, "order": TOOL_ORDER}
