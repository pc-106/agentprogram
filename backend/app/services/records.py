"""使用记录（``ragagent/data/external/records.csv``）的只读访问层。

CSV 里的换行以字面量 ``\\n`` 存储，读入时统一还原为真实换行。
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class UsageRecord:
    user_id: str
    month: str
    feature: str
    efficiency: str
    consumables: str
    comparison: str

    @property
    def is_pet_household(self) -> bool:
        return any(word in self.feature for word in ("宠物", "猫", "狗", "犬"))


def _unescape(value: str) -> str:
    text = (
        (value or "")
        .strip()
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )
    # 源数据里有 "重度-""每2天 " 这类尾随噪声，逐行清理
    return "\n".join(line.rstrip(" \t-－") for line in text.splitlines())


class RecordBook:
    """按 ``用户ID -> 月份 -> 记录`` 组织的只读视图。"""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._data: dict[str, dict[str, UsageRecord]] = {}
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        with self.path.open("r", encoding="utf-8-sig", newline="") as fh:
            for row in csv.DictReader(fh):
                user_id = (row.get("用户ID") or "").strip()
                month = (row.get("时间") or "").strip()
                if not user_id or not month:
                    continue
                self._data.setdefault(user_id, {})[month] = UsageRecord(
                    user_id=user_id,
                    month=month,
                    feature=_unescape(row.get("特征", "")),
                    efficiency=_unescape(row.get("清洁效率", "")),
                    consumables=_unescape(row.get("耗材", "")),
                    comparison=_unescape(row.get("对比", "")),
                )

    @property
    def users(self) -> list[str]:
        return sorted(self._data)

    @property
    def months(self) -> list[str]:
        return sorted({month for records in self._data.values() for month in records})

    def get(self, user_id: str, month: str) -> UsageRecord | None:
        return self._data.get(user_id, {}).get(month)

    def months_of(self, user_id: str) -> list[str]:
        return sorted(self._data.get(user_id, {}))

    def latest_month(self, user_id: str) -> str:
        months = self.months_of(user_id)
        if months:
            return months[-1]
        return self.months[-1] if self.months else "2025-12"

    def all_records(self) -> list[UsageRecord]:
        return [record for records in self._data.values() for record in records.values()]
