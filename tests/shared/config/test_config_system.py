import tempfile
from pathlib import Path

import pytest
import yaml
from pydantic import BaseModel, Field
from maa.define import LoggingLevelEnum

from mluascript.maa.config.models import MaaDeviceConfig
from mluascript.maa.lifecycle.bootstrap import resolve_tasker_stdout_level
from mluascript.shared.config.manager import load_config
from mluascript.shared.config.models import GlobalConfig
from mluascript.shared.config.registry import config as registry


@registry.registry()
class MockConfig(BaseModel):
    value_str: str = Field(default="default_str")
    value_int: int = Field(default=42)



def test_config_registry_and_loading():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "config.yaml"

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
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "config.yaml"

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
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "config.yaml"

        load_config(str(temp_path))

        global_cfg = registry.get(GlobalConfig)
        assert global_cfg.maa_stdout_level == "off"
        assert resolve_tasker_stdout_level() == LoggingLevelEnum.Off



def test_load_config_supports_maa_stdout_level_override():
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir) / "config.yaml"
        with open(temp_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"GlobalConfig": {"maa_stdout_level": "info"}}, f, allow_unicode=True)

        load_config(str(temp_path))

        global_cfg = registry.get(GlobalConfig)
        assert global_cfg.maa_stdout_level == "info"
        assert resolve_tasker_stdout_level() == LoggingLevelEnum.Info
