"""
共享文件系统路径和资源配置
提供配置目录、QSettings 实例和资源文件路径的统一管理
"""

import os
import sys
from pathlib import Path


def get_config_dir() -> Path:
    """
    获取应用配置目录路径
    首选 %LOCALAPPDATA%\\AMDS（Windows 标准应用数据目录）
    如果权限不足（如沙箱环境），回退到项目根目录下的 config/ 文件夹
    """
    local_app_data = os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local"))
    config_dir = Path(local_app_data) / "AMDS"
    try:
        config_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # 权限不足时回退到可执行文件同级目录（打包后的便携模式）
        base = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).parent.parent
        config_dir = base / "config"
        config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_qsettings() -> "QSettings":
    """
    创建一个指向配置目录下 settings.ini 的 QSettings 实例
    使用 IniFormat 而非注册表，便于打包分发和便携使用
    """
    from PyQt6.QtCore import QSettings
    config_dir = get_config_dir()
    return QSettings(str(config_dir / "settings.ini"), QSettings.Format.IniFormat)


def get_resource_path(relative_path):
    """
    获取资源文件的绝对路径
    兼容开发环境（直接访问项目目录）和 PyInstaller 打包环境（访问临时解压目录）
    """
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller 打包后的临时目录
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境：当前文件位于 src/core/，项目根目录需要向上两级
        base_path = Path(__file__).resolve().parents[2]
    return base_path / relative_path


# 资源路径常量，供其他模块直接引用
ASSETS_DIR = get_resource_path("assets")
IMAGES_DIR = ASSETS_DIR / "images"    # 角色表情、背景、Logo 等图片
AUDIO_DIR = ASSETS_DIR / "audio"      # 预设语音、铃声等音频文件
PROMPTS_DIR = ASSETS_DIR / "prompts"  # 角色 skill 与提示词配置
