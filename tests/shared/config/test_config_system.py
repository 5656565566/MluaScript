import tempfile
from contextlib import contextmanager
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, Field
from maa.define import LoggingLevelEnum

from mluascript.maa.config.models import MaaDeviceConfig
from mluascript.maa.lifecycle.bootstrap import resolve_tasker_stdout_level
from mluascript.shared.config.manager import get_runtime_dir, load_config, resolve_path_from_runtime
from mluascript.shared.config.models import GlobalConfig, WebServerConfig
from mluascript.shared.config.registry import config as registry
from mluascript.shared.logging import configure_file_logging


@registry.registry()
class MockConfig(BaseModel):
    value_str: str = Field(default="default_str")
    value_int: int = Field(default=42)


@pytest.fixture(autouse=True)
def _cleanup_file_logging():
    yield
    configure_file_logging(None)


@contextmanager
def temp_runtime_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            yield Path(temp_dir)
        finally:
            configure_file_logging(None)



def test_config_registry_and_loading():
    with temp_runtime_dir() as runtime_dir:
        temp_path = runtime_dir / "config.yaml"

        registry._is_loaded = False
        with pytest.raises(RuntimeError):
            registry.get(MockConfig)

        load_config(str(temp_path))

        mock_cfg = registry.get(MockConfig)
        assert mock_cfg.value_str == "default_str"
        assert mock_cfg.value_int == 42

        assert temp_path.exists()
        with open(temp_path, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        assert "MockConfig" in saved_data
        assert saved_data["MockConfig"]["value_str"] == "default_str"
        assert saved_data["MockConfig"]["value_int"] == 42

        custom_data = {
            "MockConfig": {
                "value_str": "custom_str",
                "value_int": 99,
            }
        }
        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(custom_data, f)

        load_config(str(temp_path))

        mock_cfg2 = registry.get(MockConfig)
        assert mock_cfg2.value_str == "custom_str"
        assert mock_cfg2.value_int == 99

        partial_data = {
            "MockConfig": {
                "value_str": "partial_str"
            }
        }
        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(partial_data, f)

        load_config(str(temp_path))

        mock_cfg3 = registry.get(MockConfig)
        assert mock_cfg3.value_str == "partial_str"
        assert mock_cfg3.value_int == 42

        with open(temp_path, "r", encoding="utf-8") as f:
            merged_data = yaml.safe_load(f)

        assert merged_data["MockConfig"]["value_str"] == "partial_str"
        assert merged_data["MockConfig"]["value_int"] == 42



def test_load_config_registers_maa_device_config():
    with temp_runtime_dir() as runtime_dir:
        temp_path = runtime_dir / "config.yaml"

        load_config(str(temp_path))

        device_cfg = registry.get(MaaDeviceConfig)
        assert isinstance(device_cfg, MaaDeviceConfig)
        assert len(device_cfg.adb_devices) >= 1

        with open(temp_path, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        assert "MaaDeviceConfig" in saved_data
        assert isinstance(saved_data["MaaDeviceConfig"]["adb_devices"], list)
        assert saved_data["MaaDeviceConfig"]["adb_devices"]



def test_load_config_supports_maa_stdout_level_default_off():
    with temp_runtime_dir() as runtime_dir:
        temp_path = runtime_dir / "config.yaml"

        load_config(str(temp_path))

        global_cfg = registry.get(GlobalConfig)
        assert global_cfg.log_dir == "./logs/app.log"
        assert global_cfg.maa_log_dir == "./logs/maa.log"
        assert global_cfg.maa_stdout_level == "off"
        assert resolve_tasker_stdout_level() == LoggingLevelEnum.Off


def test_load_config_generates_default_web_login_secret():
    with temp_runtime_dir() as runtime_dir:
        temp_path = runtime_dir / "config.yaml"

        load_config(str(temp_path))

        web_cfg = registry.get(WebServerConfig)
        assert web_cfg.username == "admin"
        assert len(web_cfg.password) == 16
        assert len(web_cfg.session_secret) == 16

        with open(temp_path, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        assert saved_data["WebServerConfig"]["username"] == "admin"
        assert saved_data["WebServerConfig"]["password"] == web_cfg.password
        assert saved_data["WebServerConfig"]["session_secret"] == web_cfg.session_secret



def test_load_config_preserves_web_settings_while_forcing_missing_passwords():
    with temp_runtime_dir() as runtime_dir:
        temp_path = runtime_dir / "config.yaml"
        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(
                {
                    "WebServerConfig": {
                        "host": "0.0.0.0",
                        "port": 19090,
                        "username": "admin",
                        "password": "",
                        "session_secret": "",
                    }
                },
                f,
                allow_unicode=True,
            )

        load_config(str(temp_path))

        web_cfg = registry.get(WebServerConfig)
        assert web_cfg.host == "0.0.0.0"
        assert web_cfg.port == 19090
        assert web_cfg.username == "admin"
        assert len(web_cfg.password) == 16
        assert len(web_cfg.session_secret) == 16

        with open(temp_path, "r", encoding="utf-8") as f:
            saved_data = yaml.safe_load(f)

        assert saved_data["WebServerConfig"]["host"] == "0.0.0.0"
        assert saved_data["WebServerConfig"]["port"] == 19090
        assert saved_data["WebServerConfig"]["password"] == web_cfg.password
        assert saved_data["WebServerConfig"]["session_secret"] == web_cfg.session_secret


def test_load_config_supports_maa_stdout_level_override():
    with temp_runtime_dir() as runtime_dir:
        temp_path = runtime_dir / "config.yaml"
        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"GlobalConfig": {"maa_stdout_level": "info"}}, f, allow_unicode=True)

        load_config(str(temp_path))

        global_cfg = registry.get(GlobalConfig)
        assert global_cfg.maa_stdout_level == "info"
        assert resolve_tasker_stdout_level() == LoggingLevelEnum.Info


def test_load_config_uses_runtime_dir_when_path_missing(monkeypatch):
    with temp_runtime_dir() as runtime_dir:
        monkeypatch.setattr("mluascript.shared.config.manager.get_runtime_dir", lambda: runtime_dir)

        load_config()

        assert (runtime_dir / "config" / "config.yaml").exists()


def test_get_runtime_dir_falls_back_to_project_root_for_source_tree():
    runtime_dir = get_runtime_dir()

    assert (runtime_dir / "pyproject.toml").exists()
    assert (runtime_dir / "src" / "mluascript").exists()


def test_resolve_path_from_runtime_supports_relative_path():
    runtime_dir = Path("F:/demo/runtime")

    resolved = resolve_path_from_runtime("./logs/app.log", runtime_dir)

    assert resolved == (runtime_dir / "logs" / "app.log").resolve()
