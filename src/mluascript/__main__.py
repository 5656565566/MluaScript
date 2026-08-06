import ctypes
import importlib
from platform import system
import keyboard

from mluascript.shared.config import load_config
from mluascript.shared.config import config as config_registry
from mluascript.shared.config.models import GlobalConfig
from mluascript.shared.logging import configure_logging, logger
from mluascript.maa.lifecycle.bootstrap import prepare_maa_runtime_environment


def _load_tui_app_class():
    module = importlib.import_module("mluascript.frontends.tui")
    return module.TuiApp


def _load_control_facade_getter():
    module = importlib.import_module("mluascript.control.facade")
    return module.get_control_facade


def main() -> None:
    if system() == "Windows":
        ctypes.windll.kernel32.SetConsoleTitleW("MluaScript 控制台")

    configure_logging(stdout=False)
    load_config()
    prepare_maa_runtime_environment()

    TuiApp = _load_tui_app_class()
    get_control_facade = _load_control_facade_getter()
    app = TuiApp()

    def _stop_all_tasks() -> None:
        try:
            logger.info("Triggered stop_all_tasks from hotkey")
            facade = get_control_facade()
            stopped = facade.stop_all_tasks()
            logger.info(f"Stopped {stopped} tasks")
            app.call_from_thread(app.notify, f"尝试停止所有任务，共停止了 {stopped} 个任务")
        except Exception as e:
            logger.error(f"Error in stop_all_tasks hotkey: {e}")

    def _run_last_task() -> None:
        try:
            logger.info("Triggered run_last_task from hotkey")
            facade = get_control_facade()
            task_id = facade.run_last_task()
            if task_id:
                logger.info(f"Started last task: {task_id}")
                app.call_from_thread(app.notify, f"已尝试启动上一个任务: {task_id}")
            else:
                logger.warning("No previous task record found")
                app.call_from_thread(app.notify, "暂无上一个任务记录", severity="warning")
        except Exception as e:
            logger.error(f"Error in run_last_task hotkey: {e}")

    try:
        global_config = config_registry.get(GlobalConfig)
        stop_key = getattr(global_config, "stop_key", None)
        start_key = getattr(global_config, "start_key", None)
        logger.info(f"Registering hotkeys: stop_key={stop_key}, start_key={start_key}")
        
        if stop_key:
            keyboard.add_hotkey(stop_key, _stop_all_tasks)
        if start_key:
            keyboard.add_hotkey(start_key, _run_last_task)
    except Exception as e:
        logger.warning(f"无法注册快捷键: {e}")

    try:
        app.run()
    finally:
        importlib.import_module("mluascript.maa.lifecycle.runtime").cleanup_maa_runtime_artifacts()


if __name__ == "__main__":
    main()
