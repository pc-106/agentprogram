"""引擎门面：按配置选择真实 Agent 或离线演示，并处理降级。

规则（默认 ``AGENT_MODE=auto``）：

* 有 Key 且调用成功 → 真实 Agent；
* 没有 Key → 直接离线演示，并在首轮对话里提示用户；
* 有 Key 但初始化/调用失败 → **先提示用户，再用离线演示把问题答完**；
* ``AGENT_MODE=real`` 时不做降级，失败直接报错，便于排查配置。
"""

from __future__ import annotations

from typing import Iterator

from ..core import config
from ..core.events import ERROR, NOTICE, STATUS, Event
from .agent_service import RealAgentService
from .demo_engine import DemoEngine
from .local_index import LocalSearchIndex
from .records import RecordBook


class EngineFacade:
    """统一入口：``mode`` 可能从 real 降级为 demo（仅 auto 模式）。"""

    def __init__(self, index: LocalSearchIndex, records: RecordBook) -> None:
        self.demo = DemoEngine(index, records)
        self.mode = config.MODE
        self.fallback = False
        self.real_error: str | None = None
        self._real: RealAgentService | None = None

    # ------------------------------------------------------------------ #
    def describe(self) -> dict:
        return {
            "mode": self.mode,
            "requested": config.MODE_REQUESTED,
            "fallback": self.fallback,
            "has_api_key": config.HAS_API_KEY,
            "real_error": self.real_error,
            "note": config.MODE_NOTE,
        }

    # ------------------------------------------------------------------ #
    def stream(
        self,
        message: str,
        intent: str = "chat",
        announce: bool = False,
    ) -> Iterator[Event]:
        """``announce=True`` 时，无 Key 的离线回答会先给用户一条说明。"""
        if self.mode == "real":
            yield from self._stream_real(message, intent)
            return

        if announce and config.MODE_REQUESTED == "auto" and not config.HAS_API_KEY:
            yield Event(
                NOTICE,
                {
                    "code": "offline_no_key",
                    "level": "warn",
                    "message": "未检测到 DASHSCOPE_API_KEY，已自动切换到离线模式回答。",
                    "detail": "离线模式使用本地知识库检索（BM25）+ 规则模板，不调用模型、不消耗额度。",
                },
            )
        yield from self.demo.stream(message, intent)

    # ------------------------------------------------------------------ #
    def _stream_real(self, message: str, intent: str) -> Iterator[Event]:
        service: RealAgentService | None = None
        try:
            if self._real is None:
                yield Event(STATUS, {"text": "正在加载 ragagent 中的 ReAct Agent…"})
                self._real = RealAgentService()
            service = self._real
        except Exception as exc:  # 缺依赖 / Key 格式错误 / 配置损坏
            self.real_error = f"{type(exc).__name__}: {exc}"
            if config.MODE_REQUESTED == "auto":
                yield from self._fallback(
                    message,
                    intent,
                    code="offline_fallback_init",
                    reason="真实模型初始化失败",
                )
                return
            yield Event(
                ERROR,
                {
                    "code": "real_agent_init_failed",
                    "message": (
                        "真实 Agent 初始化失败。请检查 DASHSCOPE_API_KEY、"
                        "依赖安装以及 ragagent/config/rag.yml 的模型名。"
                    ),
                    "detail": self.real_error[:800],
                },
            )
            return

        try:
            for event in service.stream(message, intent):
                yield event
        except Exception as exc:  # Key 无效 / 额度不足 / 网络不通 / 模型名不存在
            self.real_error = f"{type(exc).__name__}: {exc}"
            if config.MODE_REQUESTED == "auto":
                yield from self._fallback(
                    message,
                    intent,
                    code="offline_fallback_runtime",
                    reason="调用真实模型失败",
                )
                return
            yield Event(
                ERROR,
                {
                    "code": "real_agent_runtime_error",
                    "message": "调用通义千问失败，可能是 Key 无效、额度不足或网络不通。",
                    "detail": str(exc)[:800],
                },
            )

    def _fallback(self, message: str, intent: str, *, code: str, reason: str) -> Iterator[Event]:
        """通知用户 → 切离线 → 把问题答完。"""
        self.mode = "demo"
        self.fallback = True
        yield Event(
            NOTICE,
            {
                "code": code,
                "level": "warn",
                "message": f"{reason}，已自动切换到离线模式继续回答。",
                "detail": (self.real_error or "")[:500],
            },
        )
        yield from self.demo.stream(message, intent)
