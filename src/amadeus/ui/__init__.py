"""
UI模块 - 包含主窗口、角色组件、设置对话框、工作线程等
"""

from .workers import ChatWorker, TypewriterWorker, PresetSelectorWorker
from .character_widget import KurisuCharacter
from .chat_widget import ChatWidget
from .settings_dialog import SettingsDialog
from .main_window import MainWindow, SplashScreen

__all__ = [
    'ChatWorker',
    'TypewriterWorker',
    'PresetSelectorWorker',
    'KurisuCharacter',
    'ChatWidget',
    'SettingsDialog',
    'MainWindow',
    'SplashScreen',
]
