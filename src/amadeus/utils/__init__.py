"""
工具模块 - 配置管理、资源路径处理等
"""

from .config import ConfigManager, get_config, save_config, get_config_manager
from .resources import get_resource_path, ASSETS_DIR, IMAGES_DIR, AUDIO_DIR

__all__ = [
    'ConfigManager',
    'get_config',
    'save_config',
    'get_config_manager',
    'get_resource_path',
    'ASSETS_DIR',
    'IMAGES_DIR',
    'AUDIO_DIR',
]
