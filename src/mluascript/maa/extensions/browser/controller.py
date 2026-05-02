from __future__ import annotations

import io
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image
from maa.controller import CustomController
from playwright.sync_api import sync_playwright

from mluascript.shared.logging import logger


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

    def connect(self) -> bool:
        logger.info(f"Connecting to browser at {self.url}")
        try:
            if self.executable_path:
                self._launch_browser_process()
                self._wait_for_debug_endpoint()
            self.playwright = sync_playwright().start()
            self.browser = self.playwright.chromium.connect_over_cdp(self.url)
            self.page = self.browser.contexts[0].pages[0]
            self._connected = True
            return True
        except Exception as exc:
            logger.error(f"Browser connect failed: {exc}")
            return False

    def _launch_browser_process(self) -> None:
        if not self.executable_path:
            return
        args = [self.executable_path]
        args.extend(self._default_launch_args())
        args.extend(self.launch_args)
        logger.info(f"Launching browser process: {args}")
        self.process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, text=True)

    def _default_launch_args(self) -> list[str]:
        args: list[str] = []
        port = self._extract_debug_port()
        if port:
            args.append(f"--remote-debugging-port={port}")
        if self.profile_dir:
            profile_path = Path(self.profile_dir)
            profile_path.mkdir(parents=True, exist_ok=True)
            args.append(f"--user-data-dir={profile_path}")
        if self.browser_type in {"chrome", "edge", "brave", "vivaldi"}:
            args.extend(["--no-first-run", "--no-default-browser-check"])
        return args

    def _extract_debug_port(self) -> int:
        try:
            return int(str(self.url).rsplit(":", 1)[-1].rstrip("/"))
        except Exception:
            return 9222

    def _wait_for_debug_endpoint(self, timeout_seconds: float = 10.0) -> None:
        deadline = time.time() + timeout_seconds
        port = self._extract_debug_port()
        while time.time() < deadline:
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
            screenshot_bytes = self.page.screenshot()
            image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGB")
            image_array = np.array(image)[:, :, ::-1]
            return image_array
        except Exception as exc:
            logger.error(f"Browser screencap failed: {exc}")
            return np.zeros((720, 1280, 3), dtype=np.uint8)

    def click(self, x: int, y: int) -> bool:
        if not self._connected:
            return False
        try:
            self.page.mouse.click(x, y)
            logger.debug(f"Browser click at ({x}, {y})")
            return True
        except Exception as exc:
            logger.error(f"Browser click failed: {exc}")
            return False

    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int) -> bool:
        if not self._connected:
            return False
        try:
            steps = max(1, duration // 16)
            self.page.mouse.move(x1, y1)
            self.page.mouse.down()
            self.page.mouse.move(x2, y2, steps=steps)
            self.page.mouse.up()
            logger.debug(f"Browser swipe from ({x1}, {y1}) to ({x2}, {y2})")
            return True
        except Exception as exc:
            logger.error(f"Browser swipe failed: {exc}")
            return False

    def input_text(self, text: str) -> bool:
        if not self._connected:
            return False
        try:
            self.page.keyboard.type(text)
            logger.debug(f"Browser input text: {text}")
            return True
        except Exception as exc:
            logger.error(f"Browser input text failed: {exc}")
            return False

    def key_down(self, keycode: int) -> bool:
        return True

    def key_up(self, keycode: int) -> bool:
        return True
