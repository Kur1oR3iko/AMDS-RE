"""
配置管理模块
"""
import json
from pathlib import Path
from typing import Any, Optional


class ConfigManager:
    """配置管理器 - 管理应用程序配置"""
    
    DEFAULT_CONFIG = {
        "api_key": "",
        "vocu_api_key": "",
        "vocu_voice_id": "",
        "audio_mode": True,
        "max_tokens": 500,
        "model_type": "默认",
        "custom_model_url": "http://localhost:11434",
        "custom_model_name": "",
        "permanent_memory": False,
        "preset_probability": 0.3,
    }
    
    def __init__(self, config_dir: Optional[Path] = None):
        if config_dir is None:
            config_dir = Path.home() / ".amadeus"
        self.config_dir = config_dir
        self.config_file = config_dir / "config.json"
        self._ensure_config_dir()
        self._config = self._load_config()
    
    def _ensure_config_dir(self):
        self.config_dir.mkdir(parents=True, exist_ok=True)
    
    def _load_config(self) -> dict:
        if self.config_file.exists():
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    merged = self.DEFAULT_CONFIG.copy()
                    merged.update(config)
                    return merged
            except Exception as e:
                print(f"加载配置失败: {e}")
                return self.DEFAULT_CONFIG.copy()
        return self.DEFAULT_CONFIG.copy()
    
    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)
    
    def set(self, key: str, value: Any):
        self._config[key] = value
    
    def save(self):
        try:
            with open(self.config_file, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"保存配置失败: {e}")
            return False
    
    def get_all(self) -> dict:
        return self._config.copy()
    
    def set_all(self, config: dict):
        self._config.update(config)
    
    def reset(self):
        self._config = self.DEFAULT_CONFIG.copy()
        self.save()


_config_manager: Optional[ConfigManager] = None


def get_config_manager() -> ConfigManager:
    global _config_manager
    if _config_manager is None:
        _config_manager = ConfigManager()
    return _config_manager


def get_config(key: str, default: Any = None) -> Any:
    return get_config_manager().get(key, default)


def save_config(key: str, value: Any):
    manager = get_config_manager()
    manager.set(key, value)
    manager.save()
