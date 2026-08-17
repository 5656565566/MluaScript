from __future__ import annotations

import io
import queue
import socket
import subprocess
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from typing import Any, Callable

import numpy as np
from PIL import Image
from maa.controller import CustomController
from playwright.sync_api import sync_playwright

from mluascript.shared.logging import logger


_KEYCODE_MAP = {
    8: "Backspace",
    9: "Tab",
    13: "Enter",
    16: "Shift",
    17: "Control",
    18: "Alt",
    27: "Escape",
    32: " ",
    33: "PageUp",
    34: "PageDown",
    35: "End",
    36: "Home",
    37: "ArrowLeft",
    38: "ArrowUp",
    39: "ArrowRight",
    40: "ArrowDown",
    45: "Insert",
    46: "Delete",
}


class BrowserController(CustomController):
    """基于 Playwright 的浏览器控制器"""

    def __init__(
        self,
        url: str = "http://localhost:9222",
        *,
        browser_type: str = "chrome",
        executable_path: str = "",
        launch_args: list[str] | None = None,
        profile_dir: str = "",
        name: str = "",
    ) -> None:
        super().__init__()
        self.url = url
        self.browser_type = browser_type
        self.executable_path = executable_path
        self.launch_args = list(launch_args or [])
        self.profile_dir = profile_dir
        self.name = name or browser_type or url
        self._connected = False
        self.playwright: Any = None
        self.browser: Any = None
        self.page: Any = None
        self.process: subprocess.Popen[str] | None = None
        self.last_error = ""
        self._browser_tasks: queue.Queue[tuple[Callable[[], Any], Future[Any]] | None] | None = None
        self._browser_thread: threading.Thread | None = None

    def connect(self) -> bool:
        logger.info(f"Connecting to browser at {self.url}")
        try:
            if self.executable_path:
                self._launch_browser_process()
                self._wait_for_debug_endpoint()
            self._start_browser_thread()
            self._connected = True
            self.last_error = ""
            return True
        except Exception as exc:
            self.last_error = str(exc) or exc.__class__.__name__
            logger.error(f"Browser connect failed: {self.last_error}")
            self._close_transport()
            return False

    def _start_browser_thread(self) -> None:
        tasks: queue.Queue[tuple[Callable[[], Any], Future[Any]] | None] = queue.Queue()
        ready: Future[None] = Future()
        self._browser_tasks = tasks
        self._browser_thread = threading.Thread(
            target=self._browser_thread_main,
            args=(tasks, ready),
            name=f"browser-controller-{self._extract_debug_port()}",
            daemon=True,
        )
        self._browser_thread.start()
        ready.result(timeout=15.0)

    def _browser_thread_main(
        self,
        tasks: queue.Queue[tuple[Callable[[], Any], Future[Any]] | None],
        ready: Future[None],
    ) -> None:
        playwright = None
        try:
            playwright = sync_playwright().start()
            self.playwright = playwright
            self.browser = playwright.chromium.connect_over_cdp(self.url)
            self.page = self._get_active_page()
            self.page.bring_to_front()
            ready.set_result(None)

            while True:
                task = tasks.get()
                if task is None:
                    break
                operation, result = task
                if result.cancelled():
                    continue
                try:
                    result.set_result(operation())
                except Exception as exc:
                    result.set_exception(exc)
        except Exception as exc:
            if not ready.done():
                ready.set_exception(exc)
            else:
                logger.error(f"Browser worker failed: {exc}")
        finally:
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception:
                    pass
            self.playwright = None
            self.browser = None
            self.page = None

    def _submit_browser(self, operation: Callable[[], Any], *, timeout: float = 30.0) -> Any:
        tasks = getattr(self, "_browser_tasks", None)
        thread = getattr(self, "_browser_thread", None)
        if tasks is None or thread is None:
            return operation()
        if not thread.is_alive():
            raise RuntimeError("Browser worker is not running")
        if threading.current_thread() is thread:
            return operation()
        result: Future[Any] = Future()
        tasks.put((operation, result))
        return result.result(timeout=timeout)

    def _get_active_page(self) -> Any:
        if self.browser is None or not self.browser.contexts:
            raise RuntimeError("Browser CDP connection has no available context")
        context = self.browser.contexts[0]
        if context.pages:
            return next((page for page in reversed(context.pages) if page.url != "about:blank"), context.pages[-1])
        return context.new_page()

    def _current_page(self) -> Any:
        if not self._connected:
            raise RuntimeError("Browser is not connected")
        if self.page is None or self.page.is_closed():
            self.page = self._get_active_page()
        return self.page

    def _resolve_key(self, keycode: int) -> str | None:
        keycode = int(keycode)
        if keycode in _KEYCODE_MAP:
            return _KEYCODE_MAP[keycode]
        if 48 <= keycode <= 57 or 65 <= keycode <= 90:
            return chr(keycode)
        if 96 <= keycode <= 105:
            return f"Numpad{keycode - 96}"
        if 112 <= keycode <= 135:
            return f"F{keycode - 111}"
        return None

    def _close_transport(self) -> None:
        self._connected = False
        tasks = self._browser_tasks
        thread = self._browser_thread
        self._browser_tasks = None
        self._browser_thread = None
        if tasks is not None:
            tasks.put(None)
        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2.0)
        if self.process is not None and self.process.poll() is None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.process = None

    def _launch_browser_process(self) -> None:
        if not self.executable_path:
            return
        args = [self.executable_path]
        args.extend(self.launch_args)
        # Keep CDP options last so a stale browser configuration cannot override them.
        args.extend(self._default_launch_args())
        logger.info(f"Launching browser process: {args}")
        self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)

    def _default_launch_args(self) -> list[str]:
        args: list[str] = []
        port = self._extract_debug_port()
        if port:
            args.append(f"--remote-debugging-port={port}")
            args.append("--remote-debugging-address=127.0.0.1")
        profile_path = self._default_profile_dir(port)
        profile_path.mkdir(parents=True, exist_ok=True)
        args.append(f"--user-data-dir={profile_path}")
        if self.browser_type in {"chrome", "edge", "brave", "vivaldi"}:
            args.extend(["--no-first-run", "--no-default-browser-check"])
        return args

    def _default_profile_dir(self, port: int) -> Path:
        # Chrome 136+ ignores remote debugging flags for the default user profile.
        # Always use an application-owned profile instead of the user's daily browser profile.
        from mluascript.shared.config.manager import get_runtime_dir

        raw_name = self.name or self.browser_type or "browser"
        safe_name = "".join(char.lower() if char.isascii() and char.isalnum() else "-" for char in raw_name)
        safe_name = safe_name.strip("-") or "browser"
        return get_runtime_dir() / ".mluascript" / "browser" / f"{safe_name}-{port}"

    def _extract_debug_port(self) -> int:
        try:
            return int(str(self.url).rsplit(":", 1)[-1].rstrip("/"))
        except Exception:
            return 9222

    def _wait_for_debug_endpoint(self, timeout_seconds: float = 10.0) -> None:
        deadline = time.time() + timeout_seconds
        port = self._extract_debug_port()
        while time.time() < deadline:
            if self.process is not None and self.process.poll() is not None:
                raise RuntimeError(f"Browser process exited with code {self.process.returncode}")
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    return
            except OSError:
                time.sleep(0.2)
        raise TimeoutError(f"Browser debug endpoint not ready: {self.url}")

    def connected(self) -> bool:
        return self._connected

    def request_uuid(self) -> str:
        return f"browser_{self.url}"

    def screencap(self) -> np.ndarray:
        if not self._connected:
            return np.zeros((720, 1280, 3), dtype=np.uint8)

        try:
            def capture() -> np.ndarray:
                screenshot_bytes = self._current_page().screenshot()
                image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
                # Maa's native custom-controller callback requires contiguous BGR memory.
                return np.ascontiguousarray(np.array(image)[:, :, ::-1])

            return self._submit_browser(capture)
        except Exception as exc:
            logger.error(f"Browser screencap failed: {exc}")
            return np.zeros((720, 1280, 3), dtype=np.uint8)

    def click(self, x: int, y: int) -> bool:
        if not self._connected:
            return False
        try:
            self._submit_browser(lambda: self._current_page().mouse.click(x, y))
            logger.debug(f"Browser click at ({x}, {y})")
            return True
        except Exception as exc:
            logger.error(f"Browser click failed: {exc}")
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int) -> bool:
        if not self._connected:
            return False
        try:
            def drag() -> None:
                steps = max(1, duration // 16)
                mouse = self._current_page().mouse
                mouse.move(x1, y1)
                mouse.down()
                mouse.move(x2, y2, steps=steps)
                mouse.up()

            self._submit_browser(drag)
            logger.debug(f"Browser swipe from ({x1}, {y1}) to ({x2}, {y2})")
            return True
        except Exception as exc:
            logger.error(f"Browser swipe failed: {exc}")
            return False

    def input_text(self, text: str) -> bool:
        if not self._connected:
            return False
        try:
            self._submit_browser(lambda: self._current_page().keyboard.type(text))
            logger.debug(f"Browser input text: {text}")
            return True
        except Exception as exc:
            logger.error(f"Browser input text failed: {exc}")
            return False

    def click_key(self, keycode: int) -> bool:
        key = self._resolve_key(keycode)
        if key is None or not self._connected:
            return False
        try:
            self._submit_browser(lambda: self._current_page().keyboard.press(key))
            return True
        except Exception as exc:
            logger.error(f"Browser key press failed: {exc}")
            return False

    def key_down(self, keycode: int) -> bool:
        key = self._resolve_key(keycode)
        if key is None or not self._connected:
            return False
        try:
            self._submit_browser(lambda: self._current_page().keyboard.down(key))
            return True
        except Exception as exc:
            logger.error(f"Browser key down failed: {exc}")
            return False

    def key_up(self, keycode: int) -> bool:
        key = self._resolve_key(keycode)
        if key is None or not self._connected:
            return False
        try:
            self._submit_browser(lambda: self._current_page().keyboard.up(key))
            return True
        except Exception as exc:
            logger.error(f"Browser key up failed: {exc}")
            return False
