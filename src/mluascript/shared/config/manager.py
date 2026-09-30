"""LLM 配置管理加载与持久化模块"""

from __future__ import annotations

from pathlib import Path
import sys
from typing import Any, Dict, Type

import yaml
from pydantic import BaseModel, ValidationError

from mluascript.shared.config.bootstrap import ensure_config_models_registered
from mluascript.shared.config.models import GlobalConfig, WebServerConfig
from mluascript.shared.config.registry import config as registry
from mluascript.shared.logging import configure_file_logging, logger, set_log_level


def get_runtime_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "pyproject.toml").exists() and (parent / "src" / "mluascript").exists():
            return parent
    return Path.cwd()


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


def resolve_path_from_runtime(raw_path: str, runtime_dir: Path) -> Path:
    candidate = Path(raw_path).expanduser()
    if candidate.is_absolute():
        return candidate
    return (runtime_dir / candidate).resolve()


def resolve_configured_script_roots(runtime_dir: Path | None = None) -> list[Path]:
    """将 scripts_path 相对路径稳定解析到程序运行目录"""

    base_dir = (runtime_dir or get_runtime_dir()).resolve()
    try:
        configured_paths = list(registry.get(GlobalConfig).scripts_path)
    except RuntimeError:
        configured_paths = []
    roots: list[Path] = []
    for raw_path in configured_paths:
        path_text = str(raw_path).strip()
        if not path_text:
            continue
        resolved = resolve_path_from_runtime(path_text, base_dir)
        if resolved not in roots:
            roots.append(resolved)
    return roots


def _prepare_web_server_config_node(node_data: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(node_data)

    # 首次初始化或缺失敏感字段时 强制补齐随机凭据 但保留已有的 host/port 等配置
    if not str(prepared.get("password") or "").strip():
        prepared["password"] = WebServerConfig.model_fields["password"].get_default(call_default_factory=True)

    if not str(prepared.get("session_secret") or "").strip():
        prepared["session_secret"] = WebServerConfig.model_fields["session_secret"].get_default(call_default_factory=True)

    return prepared


def load_config(path: str = "") -> None:
    """统一配置加载入口"""
    ensure_config_models_registered()

    runtime_dir = get_runtime_dir()
    file = Path(path) if path else runtime_dir / "config" / "config.yaml"

    file.parent.mkdir(parents=True, exist_ok=True)
    (runtime_dir / "scripts").mkdir(parents=True, exist_ok=True)

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

        if model_cls is WebServerConfig:
            node_data = _prepare_web_server_config_node(node_data)

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
        base_dir = file.parent if path else runtime_dir
        configure_file_logging(resolve_path_from_runtime(global_cfg.log_dir, base_dir))

    logger.info(f"成功载入配置文件: {file}")
