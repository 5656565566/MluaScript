from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import uvicorn

from mluascript.frontends.web.app import create_web_app


def resolve_web_dist_dir() -> Path:
    """返回 Web 前端构建产物目录。"""

    return Path(__file__).resolve().parents[3] / "mluascript_web" / "dist"


class EmbeddedUvicornServer(uvicorn.Server):
    """由宿主应用管理信号和生命周期的 Uvicorn Server。"""

    @contextmanager
    def capture_signals(self) -> Generator[None, None, None]:
        # Textual 是进程生命周期所有者，嵌入式 Web 服务不能覆盖其信号处理器。
        yield


def create_mluascript_web_server(host: str, port: int) -> EmbeddedUvicornServer:
    """创建不接管日志和进程信号的嵌入式 Web 服务。"""

    app = create_web_app(resolve_web_dist_dir())
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level="info",
        log_config=None,
    )
    return EmbeddedUvicornServer(config)
