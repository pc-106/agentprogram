"""FastAPI 应用入口。

* ``/api/*``：后端接口（SSE 流式对话）；
* ``/``：若 ``frontend/dist`` 已构建，则直接托管 Vue 单页应用（单端口部署）。

支持三种启动方式，效果一致：

1. ``python backend/run.py``（推荐，支持 ``--port`` / ``--reload``）
2. ``cd backend && python -m uvicorn app.main:app``
3. ``python backend/app/main.py`` 或 IDE 里直接 Run 本文件（自动转交给 run.py）
"""

from __future__ import annotations

import sys
from pathlib import Path

# 直接执行本文件时 __package__ 为空，相对导入会失败：
# 先把 backend/ 补进 sys.path，再交给 run.py 用 import string 方式启动 uvicorn。
if __package__ in {None, ""}:
    _BACKEND_DIR = Path(__file__).resolve().parents[1]
    if str(_BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(_BACKEND_DIR))
    from run import main as _run_server

    _run_server()
    raise SystemExit

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from . import __version__
from .api import chat, kb, sessions, system
from .core import config
from .runtime import build_runtime

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-7s [%(name)s] %(message)s",
)
logger = logging.getLogger("app")

API_PREFIX = "/api"


@asynccontextmanager
async def lifespan(_: FastAPI):
    runtime = build_runtime()
    logger.info("mode=%s  %s", runtime.engine.mode, config.MODE_NOTE)
    yield
    logger.info("shutdown")


app = FastAPI(
    title="扫地机器人智能客服 API",
    description="Vue 3 + FastAPI 重写版；原 Streamlit 工程保留在 ragagent/ 中。",
    version=__version__,
    lifespan=lifespan,
    docs_url=f"{API_PREFIX}/docs",
    redoc_url=None,
    openapi_url=f"{API_PREFIX}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(system.router, prefix=API_PREFIX)
app.include_router(sessions.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(kb.router, prefix=API_PREFIX)


@app.exception_handler(Exception)
async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error: %s", exc)
    return JSONResponse(status_code=500, content={"ok": False, "message": str(exc)})


class SPAStaticFiles(StaticFiles):
    """找不到静态文件时回退到 index.html，支持前端 history 路由。"""

    async def get_response(self, path: str, scope):
        try:
            return await super().get_response(path, scope)
        except StarletteHTTPException as exc:
            if exc.status_code == 404:
                return await super().get_response("index.html", scope)
            raise


if config.FRONTEND_DIST.is_dir():
    app.mount("/", SPAStaticFiles(directory=config.FRONTEND_DIST, html=True), name="spa")
    logger.info("serving SPA from %s", config.FRONTEND_DIST)
else:

    @app.get("/")
    def root() -> dict:
        return {
            "ok": True,
            "app": "扫地机器人智能客服",
            "version": __version__,
            "hint": "前端尚未构建：cd frontend && pnpm install && pnpm build；开发时请访问 Vite 地址。",
            "docs": f"{API_PREFIX}/docs",
            "mode": config.MODE,
        }


if __name__ == "__main__":  # 兼容 `python -m app.main`
    from run import main as _run_server

    _run_server()
