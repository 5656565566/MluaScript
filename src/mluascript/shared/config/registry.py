"""配置注册表机制"""

from __future__ import annotations

from typing import TypeVar, Type, Dict, Callable
from pydantic import BaseModel

T = TypeVar('T', bound=BaseModel)

class ConfigRegistry:
    """配置注册表 负责管理各个模块的配置模型和实例"""
    
    def __init__(self):
        self._registry: Dict[str, Type[BaseModel]] = {}
        self._instances: Dict[Type[BaseModel], BaseModel] = {}
        self._is_loaded = False

    def registry(self) -> Callable[[Type[T]], Type[T]]:
        """
        注册 Pydantic 模型作为配置项的装饰器
        
        用法:
            @config.registry()
            class LLMConfig(BaseModel):
                ...
        """
        def decorator(cls: Type[T]) -> Type[T]:
            yaml_key = cls.__name__
            self._registry[yaml_key] = cls
            return cls
        return decorator

    def get(self, cls: Type[T]) -> T:
        """
        获取对应模型类的配置实例 自动支持类型推断
        
        用法:
            llm_cfg = config.get(LLMConfig)
        """
        if not self._is_loaded:
            raise RuntimeError("Configuration not loaded. Use load_config() to initialize.")
        
        if cls not in self._instances:
            raise KeyError(f"Configuration {cls.__name__} not found")
        
        return self._instances[cls] # type: ignore

    @property
    def registered_models(self) -> Dict[str, Type[BaseModel]]:
        """获取所有已注册的模型 Key 为 YAML 键名"""
        return self._registry
        
    def _set_instances(self, instances: Dict[Type[BaseModel], BaseModel]) -> None:
        """供配置管理器使用 注入实例化后的配置对象"""
        self._instances = instances
        self._is_loaded = True

config = ConfigRegistry()
