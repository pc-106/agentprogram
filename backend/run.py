"""启动脚本：``python run.py [--reload] [--host 127.0.0.1] [--port 8000]``。"""

from __future__ import annotations

import argparse
import socket
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import uvicorn  # noqa: E402

from app.core.config import HOST, PORT  # noqa: E402


def _port_available(host: str, port: int) -> bool:
    # 注意：不要设置 SO_REUSEADDR，Windows 上它会允许绑定到已被占用的端口，
    # 导致检测失真、真启动时才报 10048。
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="扫地机器人智能客服后端")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--reload", action="store_true", help="开发模式：代码变更自动重启")
    args = parser.parse_args()

    if not _port_available(args.host, args.port):
        print()
        print(f"[启动失败] {args.host}:{args.port} 已被占用，多半是上一次的后端还在运行。")
        print(f"  查看占用进程： netstat -ano | findstr :{args.port}")
        print(f"  结束占用进程： taskkill /PID <上一步的PID> /F")
        print(f"  或直接换端口： python run.py --port 8001")
        print()
        raise SystemExit(1)

    uvicorn.run(
        "app.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        reload_dirs=[str(BACKEND_DIR / "app")] if args.reload else None,
        log_level="info",
    )


if __name__ == "__main__":
    main()
