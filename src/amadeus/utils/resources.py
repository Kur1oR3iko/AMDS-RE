"""
资源路径处理模块
"""
import sys
from pathlib import Path


def get_resource_path(relative_path: str) -> Path:
    """
    获取资源文件路径 - 支持开发环境和PyInstaller打包环境
    
    Args:
        relative_path: 相对于项目根目录的路径
        
    Returns:
        资源文件的绝对路径
    """
    if hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
    else:
        base_path = Path(__file__).parent.parent.parent.parent
    return base_path / relative_path


ASSETS_DIR = get_resource_path("assets")
IMAGES_DIR = ASSETS_DIR / "images"
AUDIO_DIR = ASSETS_DIR / "audio"


def get_image_path(image_name: str) -> Path:
    """获取图片路径"""
    return IMAGES_DIR / image_name


def get_audio_path(audio_name: str) -> Path:
    """获取音频路径"""
    return AUDIO_DIR / f"{audio_name}.ogg"
