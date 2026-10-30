"""7 个原始工具的中文展示元信息（与 ragagent/agent/tools/agent_tools.py 一一对应）。"""

from __future__ import annotations

from typing import Any

TOOL_META: dict[str, dict[str, Any]] = {
    "rag_summarize": {
        "label": "知识库检索",
        "icon": "book-open",
        "description": "从 Chroma 向量库检索扫地/扫拖机器人资料，并由模型总结",
        "args": [{"name": "query", "label": "检索词", "type": "string"}],
        "scene": "选购建议、故障排查、使用技巧、维护保养",
    },
    "get_weather": {
        "label": "查询天气",
        "icon": "cloud-sun",
        "description": "通过高德天气接口获取指定城市实时天气（天气/气温/湿度/风力）",
        "args": [{"name": "city", "label": "城市", "type": "string"}],
        "scene": "判断当地环境是否适合机器人工作",
    },
    "get_user_location": {
        "label": "获取所在城市",
        "icon": "map-pin",
        "description": "通过高德 IP 定位获取用户所在城市（IPv6 定位失败时回退公网 IPv4）",
        "args": [],
        "scene": "用户未说明城市时自动补齐",
    },
    "get_user_id": {
        "label": "获取用户 ID",
        "icon": "user-round",
        "description": "获取当前用户的唯一标识（如 1002）",
        "args": [],
        "scene": "生成个人使用报告",
    },
    "get_current_month": {
        "label": "获取当前月份",
        "icon": "calendar-days",
        "description": "获取标准格式的当前月份（YYYY-MM）",
        "args": [],
        "scene": "生成个人使用报告",
    },
    "fetch_external_data": {
        "label": "读取使用记录",
        "icon": "database",
        "description": "读取指定用户指定月份的完整使用记录",
        "args": [
            {"name": "user_id", "label": "用户 ID", "type": "string"},
            {"name": "month", "label": "月份", "type": "string"},
        ],
        "scene": "报告生成的数据来源",
    },
    "fill_context_for_report": {
        "label": "切换报告模式",
        "icon": "file-text",
        "description": "触发中间件注入上下文，把系统提示词切换为报告写手",
        "args": [],
        "scene": "报告生成的前置动作",
    },
}

TOOL_ORDER = list(TOOL_META)
