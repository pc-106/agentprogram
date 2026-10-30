"""离线报告生成：结构、指标解读与建议都要落地。"""

from __future__ import annotations

from app.core.config import LEGACY_DIR
from app.services.records import RecordBook
from app.services.report_builder import build_report


def _book() -> RecordBook:
    return RecordBook(LEGACY_DIR / "data/external/records.csv")


def test_records_loaded() -> None:
    book = _book()
    assert len(book.users) == 10
    assert len(book.months) == 12
    record = book.get("1002", "2025-03")
    assert record is not None
    # CSV 里的字面量 \n 必须还原成真实换行
    assert "\n" in record.efficiency
    assert "覆盖率:88%" in record.efficiency


def test_report_sections() -> None:
    record = _book().get("1002", "2025-03")
    assert record is not None
    report = build_report(record, [])

    assert report.startswith("# 1002 在 2025-03 扫地机器人使用情况报告与保养建议")
    for section in (
        "## 一、使用概况",
        "## 二、数据解读",
        "## 三、保养与使用建议",
        "## 四、下月行动清单",
        "## 五、数据说明",
    ):
        assert section in report

    assert "覆盖率 88%" in report
    assert "避障失败 2 次/周" in report
    assert "- [ ]" in report


def test_report_with_pet_household() -> None:
    record = _book().get("1003", "2025-12")
    assert record is not None
    assert record.is_pet_household
    report = build_report(record, [("知识库保养建议", "每周清洗滤网并晾干。（来源：维护保养.txt）")])
    assert "宠物家庭专项" in report
    assert "胶刷寿命" in report
    assert "知识库保养建议" in report


def test_report_missing_metrics_still_has_interpretation() -> None:
    record = _book().get("1005", "2025-06")
    assert record is not None
    report = build_report(record, [])
    body = report.split("## 二、数据解读")[1].split("## 三")[0]
    assert "- " in body, "数据解读不允许为空"


def test_kb_tips_deduplicated() -> None:
    record = _book().get("1002", "2025-03")
    assert record is not None
    duplicate = "清扫前收纳地面电线、数据线与拖鞋，给宠物食盆、落地灯设置虚拟墙。"
    report = build_report(record, [("知识库保养建议", duplicate)])
    assert report.count("收纳地面电线") == 1
