"""测试引导：注入路径、隔离测试数据库、固定为离线演示模式。"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEST_DB = Path(__file__).resolve().parent / "_test_app.db"
os.environ.setdefault("APP_DB", str(TEST_DB))
os.environ.setdefault("AGENT_MODE", "demo")
os.environ.setdefault("DEMO_STREAM_DELAY", "0")  # 测试里不做流式节流

if TEST_DB.exists():
    TEST_DB.unlink()
