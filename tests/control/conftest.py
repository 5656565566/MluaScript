import importlib

import pytest

from mluascript.shared.config.registry import config
from mluascript.shared.config.bootstrap import ensure_config_models_registered


@pytest.fixture(autouse=True)
def isolate_loaded_configuration(monkeypatch):
    """集成测试可加载临时配置，但不能把配置和日志文件状态留给下一项。"""
    logging_module = importlib.import_module("mluascript.shared.logging.logger")
    previous_log_path = logging_module._file_log_path
    previous_log_level = logging_module.log_level
    ensure_config_models_registered()
    monkeypatch.setattr(config, "_instances", {model: model() for model in config.registered_models.values()})
    monkeypatch.setattr(config, "_is_loaded", True)
    try:
        yield
    finally:
        logging_module.configure_file_logging(previous_log_path)
        logging_module.set_log_level(previous_log_level)
