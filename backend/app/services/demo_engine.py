"""离线演示引擎：没有 API Key 时，用本地知识库 + 规则复现原 Agent 的能力。

它并不是"假回答"，而是把原 Agent 的 7 个工具在本地重新实现了一遍：

=============================  ==================================================
原工具                          离线实现
=============================  ==================================================
``rag_summarize``               BM25 检索 → 原文摘录 + 来源标注
``get_weather``                 与原工具一致的固定天气数据
``get_user_location``           从内置城市表抽取 / 按问题哈希稳定选取
``get_user_id``                 从问题中抽取，缺省按问题哈希稳定选取
``get_current_month``           从 ``records.csv`` 中取该用户最新月份
``fetch_external_data``         读取 ``records.csv`` 真实记录
``fill_context_for_report``     切换到"报告写手"分支
=============================  ==================================================

因此前端看到的事件流（思考 / 工具调用 / 工具结果 / 正文增量 / 引用）
与真实模式完全一致，只是正文由检索结果与规则模板合成。
"""

from __future__ import annotations

import hashlib
import os
import re
import time
from typing import Any, Callable, Iterator

from ..core.events import (
    CITATIONS,
    DELTA,
    ERROR,
    THINK,
    TOOL_CALL,
    TOOL_RESULT,
    Event,
    tool_meta,
)
from ..core.tools_meta import TOOL_META
from .local_index import Hit, LocalSearchIndex
from .records import RecordBook, UsageRecord
from .report_builder import build_report

# --------------------------------------------------------------------------- #
# 意图关键词
# --------------------------------------------------------------------------- #
REPORT_PATTERN = re.compile(r"报告|使用记录|使用情况|月报|使用报告|我的记录|使用数据")
WEATHER_PATTERN = re.compile(r"天气|气温|湿度|下雨|降雨|空气质量|雾霾|梅雨|回南天|潮湿")
GREETING_PATTERN = re.compile(r"^(你好|您好|hi|hello|嗨|在吗|你是谁|你能做什么|介绍一下|help)")
THANKS_PATTERN = re.compile(r"^(谢谢|感谢|好的|明白了|ok|收到)")

CITIES = [
    "北京", "上海", "广州", "深圳", "杭州", "西安", "武汉", "南京", "成都", "苏州",
    "无锡", "厦门", "福州", "青岛", "济南", "郑州", "太原", "重庆", "天津", "长沙",
]

MONTH_PATTERN = re.compile(r"(20\d{2})\s*[-/年.]\s*(\d{1,2})")
MONTH_ONLY_PATTERN = re.compile(r"(?<!\d)(\d{1,2})\s*月份?(?!\d)")
USER_PATTERN = re.compile(r"(?<!\d)(10\d{2})(?!\d)")

WEATHER_TEMPLATE = (
    "城市{city}天气为晴天，气温为25度，空气湿度为60%，南风1级，AQI21，最近6小时降雨概率极低。"
)

#: 离线模式没有真实 token 流，按固定节奏切块下发，让前端看到"逐字输出"。
#: 测试里用 DEMO_STREAM_DELAY=0 关闭，避免拖慢用例。
STREAM_CHUNK = int(os.getenv("DEMO_STREAM_CHUNK", "10"))
STREAM_DELAY = float(os.getenv("DEMO_STREAM_DELAY", "0.012"))


class DemoEngine:
    """把一次提问转换成与真实 Agent 相同结构的事件流。"""

    def __init__(self, index: LocalSearchIndex, records: RecordBook) -> None:
        self.index = index
        self.records = records

    # ------------------------------------------------------------------ #
    # 入口
    # ------------------------------------------------------------------ #
    def stream(self, message: str, intent: str = "chat") -> Iterator[Event]:
        text = (message or "").strip()
        if not text:
            yield Event(ERROR, {"message": "问题不能为空", "code": "empty_message"})
            return

        trace = _Trace()

        if intent == "report" or REPORT_PATTERN.search(text):
            yield from self._report_flow(text, trace)
        elif GREETING_PATTERN.search(text.lower()):
            yield from self._capability_flow()
        elif THANKS_PATTERN.search(text.lower()):
            yield from self._thanks_flow()
        elif WEATHER_PATTERN.search(text) or any(city in text for city in CITIES):
            yield from self._weather_flow(text, trace)
        else:
            yield from self._knowledge_flow(text, trace)

    # ------------------------------------------------------------------ #
    # 分支：知识库问答
    # ------------------------------------------------------------------ #
    def _knowledge_flow(self, text: str, trace: "_Trace") -> Iterator[Event]:
        yield Event(
            THINK,
            {
                "text": (
                    "先判断需求：这是一条关于扫地/扫拖机器人的使用或故障咨询，"
                    "常见回答容易给出错误参数，需要先检索本地知识库再作答。"
                )
            },
        )
        query = _extract_query(text)
        events, hits = self._run_tool(
            trace,
            "rag_summarize",
            {"query": query},
            lambda: self.index.search(query, k=3),
            note=f"用「{query}」检索知识库",
        )
        yield from events

        if not hits:
            yield from self._no_hit_answer()
            return

        yield Event(
            THINK,
            {"text": f"检索到 {len(hits)} 条相关条目，信息足够，下面整理成结论。"},
        )
        yield Event(CITATIONS, {"items": [hit.to_dict() for hit in hits]})
        yield from self._emit_answer(_compose_kb_answer(text, hits))

    # ------------------------------------------------------------------ #
    # 分支：天气 / 环境
    # ------------------------------------------------------------------ #
    def _weather_flow(self, text: str, trace: "_Trace") -> Iterator[Event]:
        city = next((item for item in CITIES if item in text), "")
        yield Event(
            THINK,
            {
                "text": (
                    "用户关心天气/湿度对机器人使用的影响。"
                    + ("问题里已经给出城市，直接查询。" if city else "缺少城市信息，先定位用户所在城市。")
                )
            },
        )
        if not city:
            events, city = self._run_tool(trace, "get_user_location", {}, lambda: _pick_city(text))
            yield from events

        events, weather = self._run_tool(
            trace, "get_weather", {"city": city}, lambda: WEATHER_TEMPLATE.format(city=city)
        )
        yield from events

        events, hits = self._run_tool(
            trace,
            "rag_summarize",
            {"query": "潮湿 环境 地面 清扫 建议"},
            lambda: self.index.search("潮湿 环境 地面 清扫 建议", k=2),
            note="补充当地环境下的使用建议",
        )
        yield from events

        if hits:
            yield Event(CITATIONS, {"items": [hit.to_dict() for hit in hits]})
        yield from self._emit_answer(_compose_weather_answer(city, weather, hits))

    # ------------------------------------------------------------------ #
    # 分支：报告生成
    # ------------------------------------------------------------------ #
    def _report_flow(self, text: str, trace: "_Trace") -> Iterator[Event]:
        yield Event(
            THINK,
            {
                "text": (
                    "识别到「生成个人使用报告」意图。按固定流程执行："
                    "获取用户 ID → 获取报告月份 → 切换报告模式 → 读取使用记录 → 补充保养建议。"
                )
            },
        )

        explicit_user = USER_PATTERN.search(text)
        events, user_id = self._run_tool(
            trace,
            "get_user_id",
            {},
            lambda: explicit_user.group(1) if explicit_user else _stable_pick(self.records.users, text),
            note="问题中已指定用户" if explicit_user else "问题未指定用户，按当前登录用户获取",
        )
        yield from events

        requested_month = _extract_month(text)
        events, month = self._run_tool(
            trace,
            "get_current_month",
            {},
            lambda: requested_month or self.records.latest_month(user_id),
            note="问题中已指定月份" if requested_month else "问题未指定月份，取最近一个月",
        )
        yield from events

        events, _ = self._run_tool(
            trace,
            "fill_context_for_report",
            {},
            lambda: "fill_context_for_report已调用",
            note="把系统提示词切换为报告写手",
        )
        yield from events

        events, record = self._run_tool(
            trace,
            "fetch_external_data",
            {"user_id": user_id, "month": month},
            lambda: self.records.get(user_id, month),
            note=f"读取 {user_id} 在 {month} 的使用记录",
        )
        yield from events

        if record is None:
            yield from self._emit_answer(
                f"没有查到用户 **{user_id}** 在 **{month}** 的使用记录。\n\n"
                f"该用户可查询的月份：{', '.join(self.records.months_of(user_id)) or '暂无'}。\n\n"
                "可以换个用户或月份再试一次。"
            )
            return

        events, hits = self._run_tool(
            trace,
            "rag_summarize",
            {"query": "耗材更换周期 保养 建议"},
            lambda: self.index.search("耗材更换周期 保养 建议", k=3),
            note="为报告补充保养建议",
        )
        yield from events

        tips = _kb_tips(hits, record, limit=2)
        if hits:
            yield Event(CITATIONS, {"items": [hit.to_dict() for hit in hits]})
        yield Event(THINK, {"text": "记录与保养资料齐备，开始撰写报告。"})
        yield from self._emit_answer(build_report(record, tips))

    # ------------------------------------------------------------------ #
    # 分支：寒暄 / 致谢
    # ------------------------------------------------------------------ #
    def _capability_flow(self) -> Iterator[Event]:
        yield Event(THINK, {"text": "用户在打招呼或了解能力范围，不需要工具，直接介绍我能做什么。"})
        yield from self._emit_answer(_capability_text())

    def _thanks_flow(self) -> Iterator[Event]:
        yield Event(THINK, {"text": "用户表示收到，简短回应并给出可继续的方向。"})
        yield from self._emit_answer(
            "不客气～ 如果还想了解具体机型的选购、日常保养或者故障自查，直接问我就行。"
            "想看这个月的使用情况，也可以说「生成我的使用报告」。"
        )

    # ------------------------------------------------------------------ #
    # 工具执行封装
    # ------------------------------------------------------------------ #
    def _run_tool(
        self,
        trace: "_Trace",
        name: str,
        args: dict[str, Any],
        fn: Callable[[], Any],
        note: str | None = None,
    ) -> tuple[list[Event], Any]:
        meta = tool_meta(name)
        call_id = trace.next_id()
        events = [
            Event(
                TOOL_CALL,
                {
                    "id": call_id,
                    "name": name,
                    "label": meta["label"],
                    "icon": meta["icon"],
                    "args": args,
                    "note": note,
                },
            )
        ]
        started = time.perf_counter()
        ok = True
        error: str | None = None
        value: Any = None
        try:
            value = fn()
        except Exception as exc:  # pragma: no cover - 防御
            ok = False
            error = str(exc)
        latency = round((time.perf_counter() - started) * 1000, 2)

        events.append(
            Event(
                TOOL_RESULT,
                {
                    "id": call_id,
                    "name": name,
                    "label": meta["label"],
                    "ok": ok,
                    "error": error,
                    "latency_ms": latency,
                    "preview": _preview_value(value),
                },
            )
        )
        return events, value

    # ------------------------------------------------------------------ #
    # 输出
    # ------------------------------------------------------------------ #
    def _emit_answer(self, text: str, size: int | None = None) -> Iterator[Event]:
        chunk_size = max(1, size or STREAM_CHUNK)
        for index in range(0, len(text), chunk_size):
            yield Event(DELTA, {"text": text[index : index + chunk_size]})
            if STREAM_DELAY > 0:
                time.sleep(STREAM_DELAY)

    def _no_hit_answer(self) -> Iterator[Event]:
        yield from self._emit_answer(
            "我在本地知识库里没有检索到能直接回答这个问题的资料。\n\n"
            "可以把问题说得更具体一点，例如：\n\n"
            "- 选购：*2000 元以内、有宠物、80㎡ 选哪种*\n"
            "- 故障：*机器人回充失败 / 边刷不转 / 拖地有水痕*\n"
            "- 保养：*滤网多久换一次 / 主刷怎么清理*\n\n"
            "也可以配置 `DASHSCOPE_API_KEY` 切换到真实 Agent 模式，让通义千问结合资料重新组织回答。"
        )


class _Trace:
    """记录工具调用 id 与次数，保证前端能按 id 配对 call/result。"""

    def __init__(self) -> None:
        self.calls = 0

    def next_id(self) -> str:
        self.calls += 1
        return f"demo_call_{self.calls}"


# --------------------------------------------------------------------------- #
# 文本工具
# --------------------------------------------------------------------------- #
def _stable_pick(options: list[str], seed: str) -> str:
    if not options:
        return ""
    digest = hashlib.md5(seed.encode("utf-8")).hexdigest()
    return options[int(digest[:8], 16) % len(options)]


def _pick_city(text: str) -> str:
    return _stable_pick(CITIES, text)


def _extract_query(text: str) -> str:
    """把口语问题压成检索词：去掉客套与句末疑问词。"""
    cleaned = re.sub(r"^(你好|您好|请问|麻烦问一下|问一下)[，,。\s]*", "", text)
    cleaned = re.sub(r"(怎么办|怎么办呢|怎么处理|如何处理|是什么原因|是什么|吗|呢|啊)[？?！!。]*$", "", cleaned)
    return cleaned.strip() or text


def _extract_month(text: str) -> str | None:
    match = MONTH_PATTERN.search(text)
    if match:
        return f"{match.group(1)}-{int(match.group(2)):02d}"
    match = MONTH_ONLY_PATTERN.search(text)
    if match:
        month = int(match.group(1))
        if 1 <= month <= 12:
            return f"2025-{month:02d}"
    return None


def _preview_value(value: Any) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, list):
        if not value:
            return ""
        first = value[0]
        if isinstance(first, Hit):
            return f"命中 {len(value)} 条：{first.chunk.title or first.chunk.source}"
        return str(first)
    if isinstance(value, UsageRecord):
        return value.feature.replace("\n", " · ")
    return str(value)


# --------------------------------------------------------------------------- #
# 回答合成
# --------------------------------------------------------------------------- #
def _capability_text() -> str:
    lines = [
        "你好，我是扫地 / 扫拖一体机器人的智能客服。我背后是一个会自己规划步骤的 Agent，",
        "遇到需要外部信息的问题时，会先调用工具再回答：\n",
    ]
    for _, meta in TOOL_META.items():
        args = "、".join(arg["label"] for arg in meta["args"]) or "无参数"
        lines.append(f"- **{meta['label']}**（{args}）：{meta['description']}")
    lines.extend(
        [
            "",
            "你可以这样问我：",
            "",
            "- 「80㎡ 有宠物，3000 元以内选哪种？」",
            "- 「机器人回充失败怎么办？」",
            "- 「滤网多久换一次？」",
            "- 「生成我的使用报告」",
        ]
    )
    return "\n".join(lines)


def _compose_kb_answer(question: str, hits: list[Hit]) -> str:
    parts = [f"我在本地知识库中检索到 {len(hits)} 条与「{question.strip()}」相关的资料：\n"]
    for index, hit in enumerate(hits, start=1):
        heading, body = _chunk_view(hit.chunk.text)
        heading = heading or hit.chunk.title or hit.chunk.source.strip()
        parts.append(f"**{index}. {heading}**\n")
        if body:
            parts.append(body)
        parts.append(f"\n<sub>来源：{hit.chunk.source.strip()} ・ 相关度 {int(hit.score * 100)}</sub>\n")
    parts.append(
        "\n---\n"
        "> 当前为**离线演示模式**：以上内容由本地 BM25 检索后原样摘录，未经大模型改写。"
        "配置 `DASHSCOPE_API_KEY` 后，会由通义千问结合这些资料生成更自然的答复。"
    )
    return "\n".join(parts)


def _compose_weather_answer(city: str, weather: str, hits: list[Hit]) -> str:
    parts = [
        f"我查了一下 **{city}** 的天气：{weather}\n",
        "对扫地 / 扫拖机器人来说，这种天气的影响主要有：\n",
        "- **晴天、湿度 60%**：适合拖地，地面干燥速度正常，拖后 10~15 分钟即可干。",
        "- **AQI 21（优）**：可以放心开窗通风，清扫时灰尘不会二次扩散。",
        "- **降雨概率极低**：不用担心回充路线湿滑，阳台清扫也可以安排。",
    ]
    if hits:
        parts.append("\n结合本地知识库的环境建议：\n")
        for index, hit in enumerate(hits, start=1):
            heading, body = _chunk_view(hit.chunk.text)
            heading = heading or hit.chunk.source.strip()
            parts.append(f"**{index}. {heading}**\n")
            if body:
                parts.append(body + "\n")
    parts.append("\n---\n> 离线演示模式：天气为内置示例数据，环境建议来自本地知识库。")
    return "\n".join(parts)


def _chunk_view(text: str) -> tuple[str, str]:
    """把一个片段拆成 (标题, 正文)，并去掉章节导航行。"""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    while lines and _is_nav_heading(lines[0]):
        lines.pop(0)
    if not lines:
        return "", ""

    if len(lines) > 1:
        return _clean_heading(lines[0]), _format_body("\n".join(lines[1:]))

    # 单行条目：故障排查类形如「故障现象：xxx；检测：yyy；修复：zzz」
    content = _strip_numbering(lines[0])
    if "；" in content:
        head, _, tail = content.partition("；")
        return _clean_heading(head), _format_body(tail)
    return _clean_heading(content), ""


_NAV_NUMBER_RE = re.compile(r"^[一二三四五六七八九十]+[、.．]")


def _is_nav_heading(line: str) -> bool:
    """章节导航行：``### 日常维护`` / ``四、维护与保养类``。"""
    stripped = line.strip()
    if stripped.startswith("#"):
        return True
    if _NAV_NUMBER_RE.match(stripped):
        return True
    return False


def _clean_heading(line: str) -> str:
    line = re.sub(r"^#{1,6}\s*", "", line.strip())
    line = _strip_numbering(line)
    line = line.replace("**", "").strip()
    return line[:60]


def _strip_numbering(line: str) -> str:
    return re.sub(r"^\d{1,3}\s*[.、)）]\s*", "", line.strip())


def _format_body(body: str) -> str:
    body = re.sub(r"^[-•]\s*", "", body.strip())
    if not body:
        return ""

    # 故障排查类：拆成「现象 / 检测 / 修复」
    segments = [seg.strip() for seg in re.split(r"[；;]", body) if seg.strip()]
    if segments and re.match(r"^(故障现象|检测|修复|原因|表现|建议|做法)", segments[0]) and len(segments) >= 2:
        bullets = []
        for seg in segments:
            match = re.match(r"^([^：:]{2,6})[：:]\s*(.+)$", seg)
            bullets.append(f"- **{match.group(1)}**：{match.group(2)}" if match else f"- {seg}")
        return "\n".join(bullets)
    return body


_ACTION_WORDS = (
    "保养", "清理", "清洗", "更换", "避免", "建议", "定期", "每周", "每月", "每日",
    "检查", "晾干", "存放", "擦拭", "冲洗",
)


def _kb_tips(hits: list[Hit], record: UsageRecord, limit: int = 2) -> list[tuple[str, str]]:
    """从知识库命中里提炼 1~2 条可直接写进报告的保养建议。"""
    tips: list[tuple[str, str]] = []
    seen: set[str] = set()
    for hit in hits:
        if len(hit.chunk.text) > 320:  # 标题行/整章内容不适合做建议
            continue
        heading, body = _chunk_view(hit.chunk.text)
        sentence = _first_sentence(body or heading)
        if not sentence or sentence in seen:
            continue
        if not any(word in sentence for word in _ACTION_WORDS):
            continue
        if not record.is_pet_household and any(word in sentence for word in ("宠物", "猫", "狗")):
            continue
        tips.append(("知识库保养建议", f"{sentence}（来源：{hit.chunk.source.strip()}）"))
        seen.add(sentence)
        if len(tips) >= limit:
            break
    return tips


def _first_sentence(text: str, max_chars: int = 110) -> str:
    flat = re.sub(r"\s+", " ", (text or "")).strip(" -•")
    flat = _strip_numbering(flat)
    if not flat:
        return ""
    parts = re.split(r"(?<=[。！？!?])", flat)
    result = ""
    for part in parts:
        if not part:
            continue
        if len(result) + len(part) > max_chars:
            break
        result += part
    return (result or flat[:max_chars]).strip()
