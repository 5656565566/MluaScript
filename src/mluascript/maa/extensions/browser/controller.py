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


# Desktop contacts select mouse buttons; pressure has no mouse equivalent.
_MOUSE_BUTTON_MAP = {0: "left", 1: "right", 2: "middle"}


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
        self._connection_lock = threading.RLock()
        self._browser_lock = threading.RLock()

    def connect(self) -> bool:
        with self._connection_lock:
            logger.info(f"Connecting to browser at {self.url}")
            launched = False
            try:
                if self._connected:
                    try:
                        healthy = self._submit_browser(lambda: self.browser is not None and self.browser.is_connected())
                    except Exception as exc:
                        logger.debug(f"Browser connection check failed: {exc}")
                        healthy = False
                    if healthy:
                        self.last_error = ""
                        return True
                if not self._stop_browser_thread():
                    self.last_error = "Previous browser worker has not stopped"
                    logger.error(f"Browser connect failed: {self.last_error}")
                    return False
                if self.executable_path:
                    if self.process is None or self.process.poll() is not None:
                        self._launch_browser_process()
                        launched = True
                    self._wait_for_debug_endpoint()
                self._start_browser_thread()
                with self._browser_lock:
                    self._connected = True
                self.last_error = ""
                return True
            except Exception as exc:
                self.last_error = str(exc) or exc.__class__.__name__
                logger.error(f"Browser connect failed: {self.last_error}")
                if launched:
                    self._close_transport()
                elif not self._stop_browser_thread():
                    logger.error("Browser worker did not stop after connection failure")
                return False

    def _start_browser_thread(self) -> None:
        tasks: queue.Queue[tuple[Callable[[], Any], Future[Any]] | None] = queue.Queue()
        ready: Future[None] = Future()
        worker = threading.Thread(
            target=self._browser_thread_main,
            args=(tasks, ready),
            name=f"browser-controller-{self._extract_debug_port()}",
            daemon=True,
        )
        with self._browser_lock:
            self._browser_tasks = tasks
            self._browser_thread = worker
        worker.start()
        ready.result(timeout=15.0)

    def _browser_thread_main(
        self,
        tasks: queue.Queue[tuple[Callable[[], Any], Future[Any]] | None],
        ready: Future[None],
    ) -> None:
        playwright = None
        running: Future[Any] | None = None
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
                if not result.set_running_or_notify_cancel():
                    continue
                running = result
                try:
                    result.set_result(operation())
                except Exception as exc:
                    result.set_exception(exc)
                finally:
                    if result.done():
                        running = None
        except Exception as exc:
            if not ready.done():
                ready.set_exception(exc)
            else:
                logger.error(f"Browser worker failed: {exc}")
        finally:
            if running is not None and not running.done():
                running.set_exception(RuntimeError("Browser worker stopped during operation"))
            if playwright is not None:
                try:
                    playwright.stop()
                except Exception as exc:
                    logger.error(f"Browser worker cleanup failed: {exc}")
            with self._browser_lock:
                self._connected = False
                self._fail_pending_browser_tasks(tasks)
                self.playwright = None
                self.browser = None
                self.page = None

    def _submit_browser(self, operation: Callable[[], Any], *, timeout: float = 30.0) -> Any:
        with self._browser_lock:
            tasks = self._browser_tasks
            thread = self._browser_thread
            if not self._connected or tasks is None or thread is None or not thread.is_alive():
                raise RuntimeError("Browser worker is not available")
            inline = threading.current_thread() is thread
            if not inline:
                result: Future[Any] = Future()
                tasks.put((operation, result))
        if inline:
            return operation()
        return result.result(timeout=timeout)

    @staticmethod
    def _fail_pending_browser_tasks(tasks: queue.Queue[tuple[Callable[[], Any], Future[Any]] | None]) -> None:
        while True:
            try:
                task = tasks.get_nowait()
            except queue.Empty:
                return
            if task is not None:
                _, result = task
                if result.set_running_or_notify_cancel():
                    result.set_exception(RuntimeError("Browser worker stopped before operation"))

    def _stop_browser_thread(self) -> bool:
        with self._browser_lock:
            self._connected = False
            tasks = self._browser_tasks
            worker = self._browser_thread
            if tasks is not None:
                self._fail_pending_browser_tasks(tasks)
                tasks.put(None)
        # The worker needs the state lock during cleanup; never hold it while joining.
        if worker is not None:
            if threading.current_thread() is worker:
                return False
            if worker.ident is not None:
                worker.join(timeout=2.0)
            if worker.is_alive():
                return False
        with self._browser_lock:
            self._browser_tasks = None
            self._browser_thread = None
        return True

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
        with self._connection_lock:
            if not self._stop_browser_thread():
                self.last_error = "Browser worker has not stopped"
                logger.error(f"Browser close failed: {self.last_error}")
                return
            if self.process is not None and self.process.poll() is None:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2.0)
                except (OSError, subprocess.TimeoutExpired) as exc:
                    self.last_error = str(exc) or exc.__class__.__name__
                    logger.error(f"Browser process cleanup failed: {self.last_error}")
                    return
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
        try:
            if not self._connected:
                raise RuntimeError("Browser is not connected")

            def capture() -> np.ndarray:
                screenshot_bytes = self._current_page().screenshot()
                image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
                # Maa's native custom-controller callback requires contiguous BGR memory.
                return np.ascontiguousarray(np.array(image)[:, :, ::-1])

            image = self._submit_browser(capture)
            self.last_error = ""
            return image
        except Exception as exc:
            self.last_error = str(exc) or exc.__class__.__name__
            logger.error(f"Browser screencap failed: {self.last_error}")
            raise RuntimeError(f"Browser screencap failed: {self.last_error}") from exc

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

    def touch_down(self, contact: int, x: int, y: int, pressure: int) -> bool:
        if not self._connected:
            return False
        button = _MOUSE_BUTTON_MAP.get(contact)
        if button is None:
            logger.warning(f"Unsupported browser mouse contact: {contact}")
            return False
        try:
            def press() -> None:
                mouse = self._current_page().mouse
                mouse.move(x, y)
                mouse.down(button=button)

            self._submit_browser(press)
            return True
        except Exception as exc:
            logger.error(f"Browser touch down failed: {exc}")
            return False

    def touch_move(self, contact: int, x: int, y: int, pressure: int) -> bool:
        if not self._connected:
            return False
        if contact not in _MOUSE_BUTTON_MAP:
            logger.warning(f"Unsupported browser mouse contact: {contact}")
            return False
        try:
            self._submit_browser(lambda: self._current_page().mouse.move(x, y))
            return True
        except Exception as exc:
            logger.error(f"Browser touch move failed: {exc}")
            return False

    def touch_up(self, contact: int) -> bool:
        if not self._connected:
            return False
        button = _MOUSE_BUTTON_MAP.get(contact)
        if button is None:
            logger.warning(f"Unsupported browser mouse contact: {contact}")
            return False
        try:
            self._submit_browser(lambda: self._current_page().mouse.up(button=button))
            return True
        except Exception as exc:
            logger.error(f"Browser touch up failed: {exc}")
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
