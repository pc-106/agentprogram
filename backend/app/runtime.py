"""运行时单例：索引、记录、引擎、服务在启动时装配一次。"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from .core import config
from .db import store
from .services.chat_service import ChatService
from .services.engine import EngineFacade
from .services.kb_service import KBService
from .services.local_index import LocalSearchIndex
from .services.records import RecordBook

logger = logging.getLogger("app.runtime")


@dataclass
class Runtime:
    index: LocalSearchIndex
    records: RecordBook
    engine: EngineFacade
    chat: ChatService
    kb: KBService
    started_at: float

    @property
    def uptime_seconds(self) -> int:
        return int(time.time() - self.started_at)


_runtime: Runtime | None = None


def build_runtime() -> Runtime:
    global _runtime
    if _runtime is not None:
        return _runtime

    config.ensure_runtime_dirs()
    store.init_db()

    index = LocalSearchIndex(config.LEGACY_DATA_DIR)
    index.build()
    records_rel = str(config.AGENT_CONF.get("external_data_path") or "data/external/records.csv")
    records = RecordBook(config.LEGACY_DIR / records_rel)
    engine = EngineFacade(index, records)
    _runtime = Runtime(
        index=index,
        records=records,
        engine=engine,
        chat=ChatService(engine),
        kb=KBService(index, records),
        started_at=time.time(),
    )
    logger.info(
        "runtime ready: mode=%s docs=%s chunks=%s build=%sms",
        engine.mode,
        index.stats()["documents"],
        index.stats()["chunks"],
        index.stats()["build_ms"],
    )
    return _runtime


def get_runtime() -> Runtime:
    return _runtime if _runtime is not None else build_runtime()
