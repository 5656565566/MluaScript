"""LLM 配置管理加载与持久化模块"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Type

import yaml
from pydantic import BaseModel, ValidationError

from mluascript.shared.config.bootstrap import ensure_config_models_registered
from mluascript.shared.config.models import GlobalConfig
from mluascript.shared.config.registry import config as registry
from mluascript.shared.logging import logger, set_log_level


def get_runtime_dir() -> Path:
    return Path.cwd()


ROOT_DIR = get_runtime_dir()


class YamlConfig:
    def __init__(self, filepath: Path | str) -> None:
        self.filepath = Path(filepath)

    def read_config(self) -> dict[str, Any] | None:
        try:
            with open(self.filepath, "r", encoding="utf-8") as file:
                config = yaml.safe_load(file)
                return config if isinstance(config, dict) else None
        except FileNotFoundError:
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Error reading YAML file: {e}")
        return None

    def write_config(self, config: dict[str, Any]) -> None:
        try:
            with open(self.filepath, "w", encoding="utf-8") as file:
                yaml.safe_dump(config, file, default_flow_style=False, allow_unicode=True)
        except yaml.YAMLError as e:
            logger.error(f"Error writing YAML file: {e}")


def load_config(path: str = "") -> None:
    """统一配置加载入口"""
    ensure_config_models_registered()

    file = Path(path) if path else ROOT_DIR / "config" / "config.yaml"

    file.parent.mkdir(parents=True, exist_ok=True)

    yaml_config = YamlConfig(file)
    raw_data = yaml_config.read_config()
    if raw_data is None:
        logger.error(f"加载配置文件 {file} 失败。")
        raw_data = {}

    instances: Dict[Type[BaseModel], BaseModel] = {}
    updated_data: Dict[str, Any] = {}

    for yaml_key, model_cls in registry.registered_models.items():
        node_data = raw_data.get(yaml_key, {})
        if not isinstance(node_data, dict):
            logger.warning(f"配置节点 '{yaml_key}' 应该是字典，重置为默认。")
            node_data = {}

        try:
            instance = model_cls(**node_data)
            instances[model_cls] = instance
            updated_data[yaml_key] = instance.model_dump(exclude={"extra"})
        except ValidationError as e:
            logger.error(f"配置节点 '{yaml_key}' 校验失败: {e}")
            instance = model_cls()
            instances[model_cls] = instance
            updated_data[yaml_key] = instance.model_dump(exclude={"extra"})

    yaml_config.write_config(updated_data)

    registry._set_instances(instances)
    global_cfg = instances.get(GlobalConfig)
    if isinstance(global_cfg, GlobalConfig):
        set_log_level(global_cfg.log_level)

    logger.info(f"成功载入配置文件: {file}")
