from __future__ import annotations

import threading
import time
from pathlib import Path

import uvicorn

from mluascript.frontends.web.app import create_web_app
from mluascript.frontends.web.state import get_web_runtime_lock, get_web_runtime_state
from mluascript.shared.config import WebServerConfig, config, load_config
from mluascript.shared.logging import logger


def get_mluascript_web_host_port() -> tuple[str, int]:
    try:
        web_cfg = config.get(WebServerConfig)
    except RuntimeError:
        load_config()
        web_cfg = config.get(WebServerConfig)
    return web_cfg.host, web_cfg.port


def get_mluascript_web_url() -> str:
    host, port = get_mluascript_web_host_port()
    state = get_web_runtime_state()
    return state.server_url or f"http://{host}:{port}"


def is_mluascript_web_running() -> bool:
    state = get_web_runtime_state()
    server = state.server
    thread = state.thread
    if server is not None:
        return bool(state.running and thread and thread.is_alive() and not getattr(server, "should_exit", False))
    return bool(state.running and thread and thread.is_alive())


def _resolve_dist_dir() -> Path:
    return Path(__file__).resolve().parents[3] / "mluascript_web" / "dist"


def _serve_forever(host: str, port: int) -> None:
    state = get_web_runtime_state()
    dist_dir = _resolve_dist_dir()
    app = create_web_app(dist_dir)
    config_obj = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config_obj)

    with get_web_runtime_lock():
        state.host = host
        state.port = port
        state.server_url = f"http://{host}:{port}"
        state.running = True
        state.should_stop = False
        state.server = server

    logger.info(f"MluaScript Web 启动于 {state.server_url}")

    try:
        server.run()
    except Exception as exc:
        logger.exception(f"MluaScript Web 服务异常退出: {exc}")
    finally:
        with get_web_runtime_lock():
            state.running = False
            state.thread = None
            state.should_stop = False
            state.server = None
        logger.info("MluaScript Web 已停止")


def run_mluascript_web_server_in_thread(host: str | None = None, port: int | None = None) -> str:
    state = get_web_runtime_state()
    if is_mluascript_web_running():
        return state.server_url or get_mluascript_web_url()

    cfg_host, cfg_port = get_mluascript_web_host_port()
    host = host or cfg_host
    port = port or cfg_port
    thread = threading.Thread(target=_serve_forever, args=(host, port), daemon=True, name="mluascript-web-server")
    with get_web_runtime_lock():
        state.thread = thread
    thread.start()

    for _ in range(20):
        time.sleep(0.1)
        if is_mluascript_web_running():
            break

    return f"http://{host}:{port}"


def stop_mluascript_web_server(timeout: float = 3.0) -> bool:
    state = get_web_runtime_state()
    thread = state.thread
    server = state.server
    if not thread:
        with get_web_runtime_lock():
            state.running = False
            state.should_stop = False
            state.server = None
        return True

    with get_web_runtime_lock():
        state.running = False
        state.should_stop = True
        if server is not None:
            server.should_exit = True

    thread.join(timeout=timeout)
    stopped = not thread.is_alive()
    if not stopped:
        logger.warning("MluaScript Web 线程尚未在超时时间内退出")
    else:
        with get_web_runtime_lock():
            state.thread = None
            state.should_stop = False
            state.server = None
    return stopped
