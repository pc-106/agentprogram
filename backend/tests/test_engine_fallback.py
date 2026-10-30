"""自动降级规则：无 Key / 调用失败都要先告知用户，再切离线答完。"""

from __future__ import annotations

import pytest

from app.core import config
from app.core.config import LEGACY_DATA_DIR, LEGACY_DIR
from app.core.events import DELTA, Event
from app.services import engine as engine_module
from app.services.engine import EngineFacade
from app.services.local_index import LocalSearchIndex
from app.services.records import RecordBook


@pytest.fixture(scope="module")
def index() -> LocalSearchIndex:
    instance = LocalSearchIndex(LEGACY_DATA_DIR)
    instance.build()
    return instance


@pytest.fixture
def facade(index: LocalSearchIndex) -> EngineFacade:
    records = RecordBook(LEGACY_DIR / "data/external/records.csv")
    return EngineFacade(index, records)


def names(events: list[Event]) -> list[str]:
    return [event.name for event in events]


def test_no_key_announces_then_answers(facade: EngineFacade, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(config, "HAS_API_KEY", False)
    monkeypatch.setattr(config, "MODE_REQUESTED", "auto")
    facade.mode = "demo"

    events = list(facade.stream("滤网多久换一次", announce=True))
    assert "notice" in names(events)
    notice = events[names(events).index("notice")].data
    assert notice["code"] == "offline_no_key"
    assert "离线模式" in notice["message"]
    assert any(event.name == DELTA for event in events)


def test_no_key_without_announce_has_no_notice(
    facade: EngineFacade, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(config, "HAS_API_KEY", False)
    monkeypatch.setattr(config, "MODE_REQUESTED", "auto")
    facade.mode = "demo"

    events = list(facade.stream("滤网多久换一次", announce=False))
    assert "notice" not in names(events)
    assert any(event.name == DELTA for event in events)


def test_init_failure_falls_back_with_notice(
    facade: EngineFacade, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("mock init failure")

    monkeypatch.setattr(config, "MODE_REQUESTED", "auto")
    monkeypatch.setattr(engine_module, "RealAgentService", Boom)
    facade.mode = "real"

    events = list(facade.stream("滤网多久换一次"))
    assert "notice" in names(events)
    notice = events[names(events).index("notice")].data
    assert notice["code"] == "offline_fallback_init"
    assert facade.mode == "demo"
    assert facade.fallback is True
    assert any(event.name == DELTA for event in events)


def test_runtime_failure_falls_back_with_notice(
    facade: EngineFacade, monkeypatch: pytest.MonkeyPatch
) -> None:
    class FailingService:
        def __init__(self) -> None:
            pass

        def stream(self, message: str, intent: str = "chat"):
            yield Event(DELTA, {"text": "半句"})
            raise RuntimeError("mock 401 invalid api key")

    monkeypatch.setattr(config, "MODE_REQUESTED", "auto")
    monkeypatch.setattr(engine_module, "RealAgentService", FailingService)
    facade.mode = "real"

    events = list(facade.stream("滤网多久换一次"))
    assert "notice" in names(events)
    notice = events[names(events).index("notice")].data
    assert notice["code"] == "offline_fallback_runtime"
    assert "mock 401" in notice["detail"]
    assert facade.mode == "demo"
    assert any(event.name == DELTA for event in events)


def test_forced_real_never_falls_back(
    facade: EngineFacade, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Boom:
        def __init__(self, *args, **kwargs):
            raise RuntimeError("mock init failure")

    monkeypatch.setattr(config, "MODE_REQUESTED", "real")
    monkeypatch.setattr(engine_module, "RealAgentService", Boom)
    facade.mode = "real"

    events = list(facade.stream("你好"))
    assert "error" in names(events)
    assert "notice" not in names(events)
    assert facade.mode == "real"
