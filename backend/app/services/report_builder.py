"""使用报告生成（离线演示模式）。

输入一条 :class:`UsageRecord` 与若干知识库保养建议，输出 Markdown 报告。
规则化写作，但所有结论都能追溯到记录里的原始字段或知识库条目。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from .records import UsageRecord

BADGE = {"good": "🟢", "warn": "🟡", "bad": "🔴", "info": "🔵"}


@dataclass
class Metrics:
    efficiency: dict[str, str] = field(default_factory=dict)
    consumables: dict[str, str] = field(default_factory=dict)
    area: int | None = None
    coverage: int | None = None
    avoid: str = ""
    missing: str = ""
    daily: str = ""
    brush_key: str = ""
    brush_value: str = ""
    filter_key: str = ""
    filter_value: str = ""
    side_value: str = ""
    dust_value: str = ""


def build_report(record: UsageRecord, tips: list[tuple[str, str]] | None = None) -> str:
    metrics = _extract(record)
    tips = tips or []
    findings, consumed = _findings(record, metrics)
    advice = _advice(record, metrics, findings)
    advice.extend(_dedupe_tips(advice, tips))
    actions = _actions(record, metrics, findings)

    lines: list[str] = []
    lines.append(f"# {record.user_id} 在 {record.month} 扫地机器人使用情况报告与保养建议")
    lines.append("")
    lines.append(f"> **用户**：{record.user_id} ・ **周期**：{record.month} ・ **场景**：{record.feature}")
    lines.append(">")
    lines.append(
        f"> 数据来源：设备使用记录 + 本地知识库保养资料 ・ 生成时间："
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}"
    )
    lines.append("")

    # ---------------- 一、使用概况 ---------------- #
    lines.append("## 一、使用概况")
    lines.append("")
    lines.append("| 维度 | 记录 |")
    lines.append("| --- | --- |")
    for label, value in (
        ("居住情况", record.feature),
        ("清洁效率", record.efficiency),
        ("耗材状态", record.consumables),
        ("同类对比", record.comparison),
    ):
        lines.append(f"| {label} | {_cell(value)} |")
    lines.append("")

    # ---------------- 二、数据解读 ---------------- #
    lines.append("## 二、数据解读")
    lines.append("")
    for status, title, detail in findings:
        lines.append(f"- {BADGE.get(status, '🔵')} **{title}**：{detail}")
    lines.append("")

    # ---------------- 三、保养建议 ---------------- #
    lines.append("## 三、保养与使用建议")
    lines.append("")
    for index, (title, detail) in enumerate(advice, start=1):
        lines.append(f"{index}. **{title}**：{detail}")
    lines.append("")

    # ---------------- 四、行动清单 ---------------- #
    lines.append("## 四、下月行动清单")
    lines.append("")
    for action in actions:
        lines.append(f"- [ ] {action}")
    lines.append("")

    # ---------------- 五、说明 ---------------- #
    lines.append("## 五、数据说明")
    lines.append("")
    lines.append("- 使用记录来自 `ragagent/data/external/records.csv`（项目内置示例数据）；")
    lines.append("- 保养条目来自本地知识库检索（BM25），已在建议中标注来源；")
    lines.append(
        "- 当前为**离线演示模式**，报告由规则模板合成。配置 `DASHSCOPE_API_KEY` 后，"
        "同一份记录会交给通义千问按报告提示词重新撰写。"
    )
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# 指标抽取
# --------------------------------------------------------------------------- #
def _extract(record: UsageRecord) -> Metrics:
    metrics = Metrics(
        efficiency=dict(_parse_pairs(record.efficiency)),
        consumables=dict(_parse_pairs(record.consumables)),
    )
    metrics.area = _area(record.feature)

    _, coverage_text = _pick(metrics.efficiency, "覆盖率")
    metrics.coverage = _pct(coverage_text)

    _, metrics.avoid = _pick(metrics.efficiency, "避障")
    _, metrics.missing = _pick(metrics.efficiency, "漏扫")
    _, metrics.daily = _pick(metrics.efficiency, "日均")

    metrics.brush_key, metrics.brush_value = _pick(metrics.consumables, "主刷", "胶刷", "滚刷")
    metrics.filter_key, metrics.filter_value = _pick(metrics.consumables, "滤网", "hepa")
    _, metrics.side_value = _pick(metrics.consumables, "边刷")
    _, metrics.dust_value = _pick(metrics.consumables, "尘盒")
    return metrics


def _findings(record: UsageRecord, metrics: Metrics) -> tuple[list[tuple[str, str, str]], set[str]]:
    findings: list[tuple[str, str, str]] = []
    consumed: set[str] = set()

    if metrics.coverage is not None:
        consumed.add("覆盖率")
        if metrics.coverage >= 92:
            findings.append(
                ("good", f"覆盖率 {metrics.coverage}%", "高于同户型平均水平，路径规划与续航都能支撑全屋清扫。")
            )
        elif metrics.coverage >= 85:
            gap = max(1, round((metrics.area or 80) * (100 - metrics.coverage) / 100))
            findings.append(
                (
                    "warn",
                    f"覆盖率 {metrics.coverage}%",
                    f"略低于 90% 的理想值，按 {metrics.area or '当前'}㎡ 估算约有 {gap}㎡ 没有被扫到。",
                )
            )
        else:
            findings.append(
                ("bad", f"覆盖率仅 {metrics.coverage}%", "明显偏低，优先排查地图完整性、家具阻挡与电量是否够用。")
            )

    if metrics.missing:
        consumed.add("漏扫区域")
        findings.append(("warn", "存在漏扫区域", f"{metrics.missing}。"))

    if metrics.avoid:
        consumed.add("避障失败")
        count = re.search(r"(\d+)\s*次", metrics.avoid)
        cause = "多由电线、拖鞋、宠物玩具等临时障碍物造成，长期如此会加速防撞条磨损。"
        if count:
            findings.append(("warn", f"避障失败 {count.group(1)} 次/周", cause))
        else:
            findings.append(("warn", "存在避障失败", f"{metrics.avoid}。{cause}"))

    if metrics.daily and metrics.area:
        consumed.add("日均清扫")
        workload = _num(metrics.daily)
        ratio = round(workload / metrics.area * 100) if workload else 0
        findings.append(
            (
                "info",
                "清扫强度",
                f"日均清扫 {metrics.daily}，约为全屋面积的 {ratio}%，"
                + ("属于高频使用。" if ratio >= 80 else "属于中低频使用，可适当提高清扫频次。"),
            )
        )

    if metrics.brush_value:
        consumed.add(metrics.brush_key)
        days = re.search(r"(\d+)\s*天", metrics.brush_value)
        if days and int(days.group(1)) <= 90:
            findings.append(
                (
                    "warn",
                    f"{metrics.brush_key}偏短",
                    f"{metrics.brush_value}，下次深度清洁时检查刷毛磨损并准备备件。",
                )
            )
        else:
            findings.append(("info", metrics.brush_key, metrics.brush_value + "。"))

    if metrics.filter_value:
        consumed.add(metrics.filter_key)
        percent = _pct(metrics.filter_value)
        if percent is not None and percent <= 50:
            findings.append(
                (
                    "warn",
                    f"{metrics.filter_key}剩余 {percent}%",
                    "接近寿命末期，继续使用会降低吸力并可能造成二次扬尘。",
                )
            )
        else:
            findings.append(("info", metrics.filter_key, metrics.filter_value + "。"))

    if metrics.side_value:
        consumed.add("边刷磨损")
        status = "warn" if ("中度" in metrics.side_value or "重度" in metrics.side_value) else "info"
        findings.append((status, "边刷磨损", f"{metrics.side_value}，会影响墙边与角落的聚尘效果。"))

    if metrics.dust_value:
        consumed.add("尘盒清理")
        findings.append(("info", "尘盒清理", f"{metrics.dust_value}，当前频率合理。"))

    if "低于同类" in record.comparison:
        findings.append(("warn", "功能使用率偏低", f"{record.comparison}。拖地模块长期闲置会加速密封圈老化。"))
    elif "优于" in record.comparison:
        findings.append(("good", "优于同类用户", f"{record.comparison}，使用习惯值得保持。"))

    # 其余指标原样呈现，避免「数据解读」出现空档
    for source, pairs in (("清洁效率", metrics.efficiency), ("耗材状态", metrics.consumables)):
        for key, value in pairs.items():
            if key in consumed or not value:
                continue
            findings.append(("info", key, value + "。"))

    if not findings:
        findings.append(("info", "记录较少", "本月可用指标不多，建议下月开启完整清扫记录后再生成报告。"))
    return findings, consumed


# --------------------------------------------------------------------------- #
# 建议
# --------------------------------------------------------------------------- #
def _advice(
    record: UsageRecord, metrics: Metrics, findings: list[tuple[str, str, str]]
) -> list[tuple[str, str]]:
    advice: list[tuple[str, str]] = []

    if metrics.coverage is not None and metrics.coverage < 92:
        advice.append(
            (
                "补齐漏扫区域",
                "在 APP 里把常活动的客厅、卧室设为「划区清扫」并开启「两次清扫」；"
                "首次建图时移开地面杂物、保持光线稳定，覆盖率通常能提升 5~10 个百分点。",
            )
        )

    if metrics.missing:
        advice.append(
            (
                "处理低矮与遮挡区域",
                f"记录中的漏扫原因是「{metrics.missing}」。沙发、床底等低矮空间先确认机身高度与越障能力，"
                "进不去的区域加装挡条或改用人工清理，避免机器人反复尝试导致卡困。",
            )
        )

    if metrics.avoid:
        advice.append(
            (
                "减少避障失败",
                "清扫前收纳地面电线、数据线与拖鞋；给宠物食盆、落地灯设置虚拟墙；"
                "每周用干布擦拭避障传感器与防撞条，保证回弹顺滑。",
            )
        )

    if metrics.filter_value:
        advice.append(
            (
                "滤网维护",
                "HEPA 滤网每 2 周用清水冲洗（不可水洗款用毛刷干清），彻底晾干后再装回；"
                "剩余寿命低于 30% 时直接更换原装滤网，避免吸力衰减和异味。",
            )
        )

    if metrics.brush_value:
        advice.append(
            (
                "主刷与毛发清理",
                "每周拆下主刷，用剪刀剪断缠绕毛发并清理两端轴承；"
                f"当前状态为「{metrics.brush_value}」，建议提前准备备用主刷，宠物家庭优先换防缠绕款。",
            )
        )

    if metrics.side_value:
        advice.append(
            (
                "边刷检查",
                f"当前边刷状态为「{metrics.side_value}」。刷毛变形可先用热水定型，"
                "断裂或明显外翻时更换，安装时注意左右边刷不要装反。",
            )
        )

    if record.is_pet_household:
        advice.append(
            (
                "宠物家庭专项",
                "每次清扫后清理主刷、尘盒与拖布，每周做一次除味消毒；"
                "耗材更换周期比普通家庭缩短约一半，优先选择胶刷与防缠绕边刷。",
            )
        )

    if "低于同类" in record.comparison:
        advice.append(
            (
                "把拖地功能用起来",
                "扫拖一体机型的拖地模块长期闲置容易导致水箱密封圈老化。"
                "建议每周至少安排 2 次「扫拖同时」，木地板出水量调至低档，拖完开窗通风。",
            )
        )

    if "优于" in record.comparison:
        advice.append(
            (
                "保持现有节奏",
                f"你的使用表现（{record.comparison}）不错，继续保持定时清扫即可；"
                "把清扫时间设在出门后，避免人机互相干扰。",
            )
        )

    advice.append(
        (
            "每月一次深度保养",
            "清理驱动轮、万向轮的缠绕物，擦拭充电触点与传感器视窗，冲洗尘盒并晾干，"
            "同时确认充电座周围 1 米内没有堆放杂物。",
        )
    )
    return advice


def _actions(record: UsageRecord, metrics: Metrics, findings: list[tuple[str, str, str]]) -> list[str]:
    actions: list[str] = []
    if metrics.avoid:
        actions.append("收纳客厅、书桌下的电线与插排，给宠物区和落地灯设置虚拟墙")
    if metrics.coverage is not None and metrics.coverage < 92:
        actions.append("把客厅与卧室设为划区清扫，并开启两次清扫")
    if metrics.missing:
        actions.append(f"检查漏扫区域（{metrics.missing}），确认机身能进入或加装挡条")
    if metrics.filter_value:
        actions.append("清洗滤网并晾干，剩余寿命低于 30% 时下单备件")
    if metrics.brush_value:
        actions.append("拆洗主刷、剪除缠绕毛发，检查两端轴承")
    if metrics.side_value:
        actions.append("检查边刷刷毛形态，必要时更换")
    if record.is_pet_household:
        actions.append("打扫后清理主刷与尘盒，每周做一次除味消毒")
    if "低于同类" in record.comparison:
        actions.append("每周安排 2 次扫拖同时，水箱出水量调到低档")
    actions.append("月底导出清扫记录，对比覆盖率是否提升")
    return actions


# --------------------------------------------------------------------------- #
# 小工具
# --------------------------------------------------------------------------- #
def _bigrams(text: str) -> set[str]:
    flat = re.sub(r"\s+", "", text or "")
    return {flat[i : i + 2] for i in range(len(flat) - 1)}


def _similar(left: str, right: str, threshold: float = 0.42) -> bool:
    a, b = _bigrams(left), _bigrams(right)
    if not a or not b:
        return False
    return len(a & b) / len(a | b) >= threshold


def _dedupe_tips(
    existing: list[tuple[str, str]], tips: list[tuple[str, str]]
) -> list[tuple[str, str]]:
    """知识库建议若与规则建议高度重复，则丢弃，避免报告啰嗦。"""
    kept: list[tuple[str, str]] = []
    for title, detail in tips:
        if any(_similar(detail, old_detail) for _, old_detail in existing + kept):
            continue
        kept.append((title, detail))
    return kept


def _parse_pairs(block: str) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in (block or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        match = re.match(r"^([^：:]{1,12})[：:]\s*(.+)$", line)
        if match:
            key = match.group(1).strip()
            value = re.sub(r"[-\s]+$", "", match.group(2).strip())
            pairs.append((key, value))
        else:
            pairs.append((line, ""))
    return pairs


def _pick(pairs: dict[str, str], *keywords: str) -> tuple[str, str]:
    for key, value in pairs.items():
        lowered = key.lower()
        if any(keyword.lower() in lowered for keyword in keywords):
            return key, value
    return "", ""


def _cell(text: str) -> str:
    return (text or "—").replace("\n", "<br>").replace("|", "\\|")


def _area(text: str) -> int | None:
    match = re.search(r"(\d{2,4})\s*㎡", text or "")
    return int(match.group(1)) if match else None


def _pct(text: str) -> int | None:
    match = re.search(r"(\d{1,3})\s*%", text or "")
    return int(match.group(1)) if match else None


def _num(text: str) -> float:
    match = re.search(r"(\d+(?:\.\d+)?)", text or "")
    return float(match.group(1)) if match else 0.0
