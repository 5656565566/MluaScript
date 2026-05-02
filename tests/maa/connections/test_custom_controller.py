from __future__ import annotations

import os
from pathlib import Path

import pytest
import numpy as np

from maa.controller import CustomController
from maa.library import Library

from mluascript.maa.lifecycle.binding import bind_controller
from mluascript.maa.lifecycle.runtime import MaaContext
from mluascript.maa.types import MaaContextState, MaaPaths

def find_maafw_path() -> Path:
    env_path = os.environ.get("MAAFW_DIR")
    if env_path:
        path = Path(env_path).resolve()
        if path.exists() and path.is_dir():
            return path
    
    cwd_maafw = Path.cwd() / "maafw"
    if cwd_maafw.exists() and cwd_maafw.is_dir():
        return cwd_maafw.resolve()
    
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / ".git").exists() or (parent / "pyproject.toml").exists():
            project_maafw = parent / "maafw"
            if project_maafw.exists() and project_maafw.is_dir():
                return project_maafw.resolve()
            break  # 找到项目根目录后停止向上查找
    
    test_file_dir = Path(__file__).resolve().parent
    for up_level in [1, 2, 3]:
        candidate = test_file_dir.parents[up_level - 1] / "maafw"
        if candidate.exists() and candidate.is_dir():
            return candidate.resolve()
    
    default_path = Path("maafw").resolve()
    return default_path

MAAFW_PATH = find_maafw_path()
HAS_MAAFW = MAAFW_PATH.exists() and MAAFW_PATH.is_dir()

class EmptyController(CustomController):
    """空壳控制器"""
    
    def connect(self) -> bool:
        return True
    
    def connected(self) -> bool:
        return True
    
    def request_uuid(self) -> str:
        return "empty_123"
    
    def start_app(self, intent: str) -> bool:
        """启动应用"""
        print(f"[EmptyController] start_app: {intent}")
        return True
    
    def stop_app(self, intent: str) -> bool:
        """停止应用"""
        print(f"[EmptyController] stop_app: {intent}")
        return True
    
    def screencap(self) -> np.ndarray:
        """返回一个空白测试图像"""
        # 创建一个 720x1080 的黑色图像
        return np.zeros((1080, 720, 3), dtype=np.uint8)
    
    def click(self, x: int, y: int) -> bool:
        """点击"""
        print(f"[EmptyController] click: ({x}, {y})")
        return True
    
    def swipe(self, x1: int, y1: int, x2: int, y2: int, duration: int) -> bool:
        """滑动"""
        print(f"[EmptyController] swipe: ({x1},{y1}) -> ({x2},{y2}), duration={duration}")
        return True
    
    def touch_down(self, contact: int, x: int, y: int, pressure: int) -> bool:
        """触摸按下"""
        print(f"[EmptyController] touch_down: contact={contact}, ({x},{y}), pressure={pressure}")
        return True
    
    def touch_move(self, contact: int, x: int, y: int, pressure: int) -> bool:
        """触摸移动"""
        print(f"[EmptyController] touch_move: contact={contact}, ({x},{y}), pressure={pressure}")
        return True
    
    def touch_up(self, contact: int) -> bool:
        """触摸抬起"""
        print(f"[EmptyController] touch_up: contact={contact}")
        return True
    
    def click_key(self, keycode: int) -> bool:
        """按键点击"""
        print(f"[EmptyController] click_key: {keycode}")
        return True
    
    def input_text(self, text: str) -> bool:
        """输入文本"""
        print(f"[EmptyController] input_text: {text}")
        return True
    
    def key_down(self, keycode: int) -> bool:
        """按键按下"""
        print(f"[EmptyController] key_down: {keycode}")
        return True
    
    def key_up(self, keycode: int) -> bool:
        """按键抬起"""
        print(f"[EmptyController] key_up: {keycode}")
        return True
    
    # def get_features(self) -> int:
    #     return super().get_features()
    
    # def scroll(self, dx: int, dy: int) -> bool:
    #     return super().scroll(dx, dy)
    
    # def relative_move(self, dx: int, dy: int) -> bool:
    #     return super().relative_move(dx, dy)
    
    # def shell(self, cmd: str, timeout: int) -> Optional[str]:
    #     return super().shell(cmd, timeout)
    
    # def inactive(self) -> bool:
    #     return super().inactive()
    
    # def get_custom_info(self) -> Dict[str, Any]:
    #     return super().get_custom_info()


@pytest.mark.skipif(
    not HAS_MAAFW, 
    reason=f"MAA 框架库不存在: {MAAFW_PATH} 请设置正确的 MAAFW_DIR 环境变量"
)
def test_custom_controller_connection():
    Library.open(MAAFW_PATH)

    context = MaaContext(
        paths=MaaPaths(library_dir=MAAFW_PATH, resource_dir=Path(".")),
        state=MaaContextState(),
    )

    controller = EmptyController()
    job = controller.post_connection()
    job.wait()
    
    assert job.succeeded

    bind_controller(context, controller)

    assert context.controller is controller
    assert context.state.connected is True
