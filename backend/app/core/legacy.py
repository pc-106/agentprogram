"""ragagent 兼容层：在不修改原代码一行的前提下让原工程可被导入/调用。

原工程存在三处「配置与文件不一致」的缺陷，直接运行会失败：

===========  ==========================================  ==========================
#            原代码里写的内容                                实际文件
===========  ==========================================  ==========================
1            ``from utils.path_tools import get_abs_path``  ``utils/path_tool.py``
2            读取 ``config/rag.yaml`` 等                    ``config/*.yml``
3            提示词路径 ``prompts/main_prompt.txt``          ``prompt/main_prompt.txt``
===========  ==========================================  ==========================

本模块通过 **运行时模块注入**（``sys.path`` + ``sys.modules``）修正上述三点：

* ``sys.modules["utils.path_tools"]`` 指向真实的 ``utils.path_tool``；
* ``sys.modules["utils.config_handler"]`` 换成读取 ``*.yml``、并修正提示词目录的替代模块。

原文件一个字节都不会被改动，工程目录也保持原样（可随时单独运行/对比）。
"""

from __future__ import annotations

import importlib
import os
import sys
import types
from pathlib import Path
from typing import Any

from .config import LEGACY_DIR, RUNTIME_DIR

_prepared = False
_notes: list[str] = []

#: 原配置里写错的目录名 -> 实际目录名
DIR_ALIASES = {"prompts": "prompt"}
PROMPT_KEYS = ("main_prompt_path", "rag_summarize_prompt_path", "report_prompt_path")


def _read_yaml(relative_path: str) -> dict[str, Any]:
    import yaml

    path = LEGACY_DIR / relative_path
    if not path.is_file():
        return {}
    try:
        with path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}


def _normalize_prompt_path(relative: str) -> str:
    """把 ``prompts/xxx`` 修正为实际存在的 ``prompt/xxx``。"""
    rel = str(relative).replace("\\", "/").lstrip("/")
    if (LEGACY_DIR / rel).is_file():
        return rel
    head, _, tail = rel.partition("/")
    alias = DIR_ALIASES.get(head)
    if alias:
        candidate = f"{alias}/{tail}"
        if (LEGACY_DIR / candidate).is_file():
            return candidate
    return rel


def _build_config_module() -> types.ModuleType:
    module = types.ModuleType("utils.config_handler")
    rag_conf = _read_yaml("config/rag.yml")
    chroma_conf = _read_yaml("config/chroma.yml")
    prompts_conf = _read_yaml("config/prompts.yml")
    agent_conf = _read_yaml("config/agent.yml")

    for key in PROMPT_KEYS:
        value = prompts_conf.get(key)
        if value:
            normalized = _normalize_prompt_path(value)
            if normalized != value:
                _notes.append(f"提示词路径修正：{value} -> {normalized}")
            prompts_conf[key] = normalized

    # 原工程用相对路径（chroma_db / md5.text / data），依赖"在 ragagent 目录下启动"。
    # 新版从 backend/ 启动，这里统一改成绝对路径，避免把向量库建到错误位置。
    for key in ("persist_directory", "data_path", "md5_hex_store"):
        value = chroma_conf.get(key)
        if isinstance(value, str) and value and not os.path.isabs(value):
            chroma_conf[key] = str((LEGACY_DIR / value).resolve())
            _notes.append(f"绝对化路径：{key} = {chroma_conf[key]}")

    external_path = agent_conf.get("external_data_path")
    if isinstance(external_path, str) and external_path and not os.path.isabs(external_path):
        agent_conf["external_data_path"] = str((LEGACY_DIR / external_path).resolve())

    def _loader(relative_path: str):
        def load(config_path: str | None = None, encoding: str = "utf-8") -> dict[str, Any]:
            target = config_path or str(LEGACY_DIR / relative_path)
            import yaml

            with open(target, "r", encoding=encoding) as fh:
                data = yaml.safe_load(fh)
            return data if isinstance(data, dict) else {}

        return load

    module.rag_conf = rag_conf
    module.chroma_conf = chroma_conf
    module.prompts_conf = prompts_conf
    module.agent_conf = agent_conf
    module.load_rag_config = _loader("config/rag.yml")
    module.load_chroma_config = _loader("config/chroma.yml")
    module.load_prompts_config = _loader("config/prompts.yml")
    module.load_agent_config = _loader("config/agent.yml")
    return module


def prepare_legacy_imports() -> None:
    """注入兼容模块，使 ``agent.*`` / ``rag.*`` / ``utils.*`` 可正常 import。"""
    global _prepared
    if _prepared:
        return

    root = str(LEGACY_DIR)
    if root not in sys.path:
        sys.path.insert(0, root)
        _notes.append(f"已将 {root} 加入 sys.path")

    # 缺陷 1：原码 ``from utils.path_tools import ...`` 中的拼写错误
    if "utils.path_tools" not in sys.modules:
        real = importlib.import_module("utils.path_tool")
        sys.modules["utils.path_tools"] = real
        _notes.append("别名注册：utils.path_tools -> utils.path_tool")

    # 缺陷 2 & 3：配置扩展名 + 提示词目录
    if "utils.config_handler" not in sys.modules:
        sys.modules["utils.config_handler"] = _build_config_module()
        _notes.append("配置注入：*.yml 读取 + prompts/ -> prompt/ 路径修正")

    _redirect_agent_logs()
    _prepared = True


def _redirect_agent_logs() -> None:
    """把原工程 logger 的文件输出改到 backend/data/logs。

    原 ``utils/logger_handler.py`` 会把日志写进 ``ragagent/logs/``，
    这样每跑一次真实模式就会往原工程目录里追加内容。这里保持控制台输出不变，
    只把文件 handler 换到新后端自己的数据目录，原目录保持只读状态。
    """
    import logging
    from datetime import datetime

    try:
        from utils import logger_handler
    except Exception:  # 原工程缺少该模块时忽略
        return

    logger = logger_handler.logger
    if getattr(logger, "_web_redirected", False):
        return

    log_dir = RUNTIME_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    target = log_dir / f"agent_{datetime.now():%Y%m%d}.log"

    original_files: list[Path] = []
    for handler in list(logger.handlers):
        if isinstance(handler, logging.FileHandler):
            original_files.append(Path(getattr(handler, "baseFilename", "") or ""))
            logger.removeHandler(handler)
            try:
                handler.close()
            except Exception:
                pass

    file_handler = logging.FileHandler(target, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logger_handler.DEFAULT_LOG_FORMAT)
    logger.addHandler(file_handler)
    logger.propagate = False  # 避免与根 logger 重复打印
    logger._web_redirected = True  # type: ignore[attr-defined]

    # 导入 logger_handler 时会顺手创建空的当日日志文件，这里清掉，保持原目录干净
    for path in original_files:
        try:
            if path.is_file() and path.stat().st_size == 0:
                path.unlink()
        except OSError:
            pass

    _notes.append(f"日志重定向：ragagent/logs -> {log_dir}")


def legacy_report() -> dict[str, Any]:
    """返回兼容层的工作摘要，供 /api/system/config 展示。"""
    return {
        "legacy_dir": str(LEGACY_DIR),
        "exists": LEGACY_DIR.is_dir(),
        "prepared": _prepared,
        "notes": list(_notes),
    }


def import_agent_class():
    """导入原工程的 ``ReAct_Agent``（会先注入兼容层）。"""
    prepare_legacy_imports()
    from agent.react_agent import ReAct_Agent  # noqa: WPS433 (运行时导入)

    return ReAct_Agent


def prompt_preview(name: str = "main") -> str:
    """读取原工程提示词原文，供前端「提示词」面板展示。"""
    mapping = {
        "main": "prompt/main_prompt.txt",
        "rag": "prompt/rag_summarize.txt",
        "report": "prompt/report_prompt.txt",
    }
    rel = mapping.get(name)
    if not rel:
        return ""
    path: Path = LEGACY_DIR / rel
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""
