"""Main AMDS window composition and settings application."""

from __future__ import annotations

import json
import os
import sys

from openai import OpenAI
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from core.app_config import (
    DEFAULT_MODEL,
    DEFAULT_PRESET_AUDIO_PROBABILITY,
    DEFAULT_VOCU_ASYNC_MODE,
    DEFAULT_VOCU_FLASH_MODE,
    LEGACY_MODEL_MAP,
)
from core.resources import AUDIO_DIR, IMAGES_DIR, get_config_dir, get_qsettings
from services.ai_manager import AIChatManager
from services.audio_player import AudioPlayer
from services.voice_dialog import VoiceDialog
from ui.character import KurisuCharacter
from ui.chat_widget import ChatWidget
from ui.debug_window import DebugTitleLabel, DebugWindow
from ui.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amadeus - 牧濑红莉栖")
        self.setMinimumSize(900, 600)

        icon_path = IMAGES_DIR / "ic_launcher.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

        self.setStyleSheet(
            """
            QMainWindow {
                background-color: #2C1810;
            }
            """
        )

        self.debug_window = None
        self.setup_ui()

    def setup_ui(self):
        """Build the main window UI."""
        central_widget = QWidget()
        central_widget.setObjectName("mainCentralWidget")
        central_widget.setStyleSheet("#mainCentralWidget { background-color: #2C1810; }")
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)

        left_panel = QWidget()
        left_panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        left_panel.setStyleSheet("background: transparent;")
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.character = KurisuCharacter()
        left_layout.addWidget(self.character, alignment=Qt.AlignmentFlag.AlignCenter)
        main_layout.addWidget(left_panel, 1)

        right_panel = QWidget()
        right_panel.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        right_panel.setStyleSheet("background: transparent;")
        right_layout = QVBoxLayout(right_panel)

        title_widget = QWidget()
        title_widget.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        title_widget.setStyleSheet("background: transparent;")
        title_layout = QHBoxLayout(title_widget)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.logo_label = QLabel()
        logo_pixmap = QPixmap(str(IMAGES_DIR / "logo1.png"))
        if not logo_pixmap.isNull():
            scaled_logo = logo_pixmap.scaled(
                48,
                48,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.logo_label.setPixmap(scaled_logo)
        title_layout.addWidget(self.logo_label)

        self.title_label = DebugTitleLabel("Amadeus System")
        self.title_label.setToolTip("连续点击三次打开调试窗口")
        self.title_label.triple_clicked.connect(self.show_debug_window)
        self.title_label.setStyleSheet(
            """
            QLabel {
                color: #D2691E;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
            """
        )
        title_layout.addWidget(self.title_label)

        self.settings_button = QPushButton()
        settings_pixmap = QPixmap(str(IMAGES_DIR / "logo39.png"))
        if not settings_pixmap.isNull():
            scaled_pixmap = settings_pixmap.scaled(
                96,
                96,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            settings_icon = QIcon(scaled_pixmap)
            self.settings_button.setIcon(settings_icon)
            self.settings_button.setIconSize(scaled_pixmap.size())
        self.settings_button.setFixedSize(120, 120)
        self.settings_button.setStyleSheet(
            """
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(139, 69, 19, 0.3);
                border-radius: 5px;
            }
            """
        )
        self.settings_button.setToolTip("设置")
        self.settings_button.clicked.connect(self.open_settings)
        title_layout.addWidget(self.settings_button)

        right_layout.addWidget(title_widget)

        self.chat = ChatWidget()
        self.chat.character = self.character
        right_layout.addWidget(self.chat, 1)

        main_layout.addWidget(right_panel, 2)

    def show_debug_window(self):
        """Show the floating debug log window."""
        if self.debug_window is None:
            self.debug_window = DebugWindow()
            self.debug_window.closed.connect(self._on_debug_window_closed)
        self.debug_window.refresh()
        self.debug_window.show()
        self.debug_window.raise_()
        self.debug_window.activateWindow()

    def _on_debug_window_closed(self):
        self.debug_window = None

    def play_tone(self):
        """Play the startup tone, then chain into greeting playback."""
        print("[启动] 开始播放启动音效...")
        tone_path = AUDIO_DIR / "tone.ogg"
        print(f"[启动] 启动音效路径: {tone_path}")
        print(f"[启动] 启动音效文件存在: {tone_path.exists()}")
        if tone_path.exists():
            print("[启动] 创建 AudioPlayer 实例...")
            self.tone_player = AudioPlayer(tone_path)
            self.tone_player.finished.connect(self.play_greeting)
            print("[启动] 开始播放启动音效...")
            self.tone_player.start()
        else:
            print("[启动] 启动音效文件不存在")

    def play_greeting(self):
        """Play a greeting line after the startup tone."""
        print("[启动] 开始播放问候语...")
        if self.chat.permanent_memory:
            print("[启动] 永久记忆已开启，跳过启动问候语")
            return

        greeting = VoiceDialog.get_random_greeting()
        print(f"[启动] 随机问候语: {greeting}")

        greeting_text = self.chat.get_response_text(greeting)
        print(f"[启动] 问候语文本: {greeting_text}")
        self.chat.add_message("牧濑红莉栖", greeting_text, "#8B4513")

        audio_path = AUDIO_DIR / f"{greeting}.ogg"
        print(f"[启动] 问候语音频路径: {audio_path}")
        print(f"[启动] 问候语音频文件存在: {audio_path.exists()}")
        if not audio_path.exists():
            print("[启动] 问候语音频文件不存在")
            return

        japanese_text = VoiceDialog.get_japanese_text_for_audio(greeting)
        if japanese_text:
            self.character.set_japanese_text(japanese_text)

        emotion = VoiceDialog.get_emotion_for_audio(greeting)
        print(f"[启动] 问候语表情: {emotion}")
        self.character.set_emotion(emotion)

        print("[启动] 创建问候语 AudioPlayer 实例...")
        self.player = AudioPlayer(audio_path)
        self.player.started.connect(self.character.start_speaking)
        self.player.finished.connect(self.character.stop_speaking)
        print("[启动] 开始播放问候语音频...")
        self.player.start()

    def open_settings(self):
        """Open the settings dialog and persist the user's changes."""
        current_api_key = self.chat.ai_manager.API_KEY
        qsettings = get_qsettings()

        vocu_api_key = qsettings.value("vocu_api_key", "")
        vocu_voice_id = qsettings.value("vocu_voice_id", "")
        audio_mode = qsettings.value("audio_mode", True, type=bool)
        max_tokens = qsettings.value("max_tokens", 200, type=int)
        preset_audio_probability = qsettings.value(
            "preset_audio_probability",
            DEFAULT_PRESET_AUDIO_PROBABILITY,
            type=int,
        )
        vocu_async_mode = qsettings.value(
            "vocu_async_mode",
            DEFAULT_VOCU_ASYNC_MODE,
            type=bool,
        )
        vocu_flash_mode = qsettings.value(
            "vocu_flash_mode",
            DEFAULT_VOCU_FLASH_MODE,
            type=bool,
        )

        print(
            f"加载 Vocu 设置: api_key={'*' * len(vocu_api_key) if vocu_api_key else '空'}, "
            f"voice_id={vocu_voice_id or '空'}, audio_mode={audio_mode}, max_tokens={max_tokens}, "
            f"preset_probability={preset_audio_probability}, vocu_async_mode={vocu_async_mode}, "
            f"vocu_flash_mode={vocu_flash_mode}"
        )

        dialog = SettingsDialog(self, current_api_key, vocu_api_key, vocu_voice_id, audio_mode, max_tokens)
        result = dialog.exec()
        print(f"设置对话框结果: {result}, Accepted={QDialog.DialogCode.Accepted}")

        if result != QDialog.DialogCode.Accepted:
            return

        settings = dialog.get_settings()
        print(
            f"获取设置: api_key={'*' * len(settings['api_key']) if settings['api_key'] else '空'}, "
            f"vocu_api_key={'*' * len(settings['vocu_api_key']) if settings['vocu_api_key'] else '空'}, "
            f"vocu_voice_id={settings['vocu_voice_id'] or '空'}, audio_mode={settings['audio_mode']}, "
            f"max_tokens={settings['max_tokens']}"
        )

        if settings["api_key"]:
            self.chat.ai_manager.API_KEY = settings["api_key"]
            self._save_api_key(settings["api_key"])

        self.chat.ai_manager.MODEL = LEGACY_MODEL_MAP.get(settings["model"], settings["model"])
        self.chat.ai_manager.current_model = self.chat.ai_manager.MODEL
        print(f"模型已更新为: {settings['model']}")

        if settings["model_type"] == "自定义":
            current_history = (
                self.chat.ai_manager.conversation_history
                if hasattr(self.chat.ai_manager, "conversation_history")
                else []
            )
            self.chat.ai_manager = AIChatManager(
                model_type=settings["model_type"],
                custom_model_url=settings["custom_model_url"],
                custom_model_name=settings["custom_model_name"],
            )
            self.chat.ai_manager.conversation_history = current_history
            print(
                f"[设置] 已切换到自定义模型: {settings['custom_model_name']} "
                f"at {settings['custom_model_url']}"
            )
        else:
            self.chat.ai_manager.client = OpenAI(
                base_url=self.chat.ai_manager.BASE_URL,
                api_key=self.chat.ai_manager.API_KEY,
            )
            print(f"[设置] 已切换到默认模型: {settings['model']}")

        old_permanent_memory = self.chat.permanent_memory
        new_permanent_memory = settings.get("permanent_memory", False)

        self._save_vocu_settings(
            settings["vocu_api_key"],
            settings["vocu_voice_id"],
            settings["audio_mode"],
            settings["max_tokens"],
            settings["model"],
            settings["model_type"],
            settings["custom_model_url"],
            settings["custom_model_name"],
            new_permanent_memory,
            settings["preset_audio_probability"],
            settings["vocu_async_mode"],
            settings["vocu_flash_mode"],
        )

        self.chat.permanent_memory = new_permanent_memory
        if self.chat.ai_manager:
            self.chat.ai_manager.permanent_memory = new_permanent_memory

        if old_permanent_memory and not new_permanent_memory:
            self._handle_disable_permanent_memory(settings)
        elif not old_permanent_memory and new_permanent_memory and self.chat.ai_manager:
            print("永久记忆已开启，开始加载历史记录...")
            self.chat.ai_manager.load_conversation()

        self.chat._init_audio_generator()
        print(f"设置已更新: API 密钥{'已保存' if settings['api_key'] else '已清空'}")

    def _handle_disable_permanent_memory(self, settings: dict):
        """Confirm disabling permanent memory and clear history if accepted."""
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle("确认关闭永久记忆")
        msg_box.setText("关闭永久记忆会清除当前保存的聊天记录，确定继续吗？")

        confirm_button = msg_box.addButton("确认关闭", QMessageBox.ButtonRole.AcceptRole)
        msg_box.addButton("取消", QMessageBox.ButtonRole.RejectRole)
        msg_box.exec()

        if msg_box.clickedButton() == confirm_button:
            print("永久记忆已关闭，清理对话历史并重启...")
            if self.chat.ai_manager:
                self.chat.ai_manager.clear_conversation()
            QApplication.instance().quit()
            os.execv(sys.executable, [sys.executable] + sys.argv)
            return

        print("用户取消关闭永久记忆，恢复开启状态")
        self.chat.permanent_memory = True
        if self.chat.ai_manager:
            self.chat.ai_manager.permanent_memory = True
        self._save_vocu_settings(
            settings["vocu_api_key"],
            settings["vocu_voice_id"],
            settings["audio_mode"],
            settings["max_tokens"],
            settings["model"],
            settings["model_type"],
            settings["custom_model_url"],
            settings["custom_model_name"],
            True,
            settings["preset_audio_probability"],
            settings["vocu_async_mode"],
            settings["vocu_flash_mode"],
        )

    def _save_api_key(self, api_key: str):
        try:
            config_dir = get_config_dir()
            config_file = config_dir / "config.json"
            with open(config_file, "w", encoding="utf-8") as file:
                json.dump({"api_key": api_key}, file)
        except Exception as exc:
            print(f"保存 API 配置失败: {exc}")

    def _load_api_key(self) -> str:
        try:
            config_file = get_config_dir() / "config.json"
            if config_file.exists():
                with open(config_file, "r", encoding="utf-8") as file:
                    config = json.load(file)
                    return config.get("api_key", "")
        except Exception as exc:
            print(f"加载 API 配置失败: {exc}")
        return ""

    def _save_vocu_settings(
        self,
        api_key: str,
        voice_id: str,
        audio_mode: bool = True,
        max_tokens: int = 500,
        model: str = DEFAULT_MODEL,
        model_type: str = "默认",
        custom_model_url: str = "http://localhost:11434",
        custom_model_name: str = "",
        permanent_memory: bool = False,
        preset_audio_probability: int = DEFAULT_PRESET_AUDIO_PROBABILITY,
        vocu_async_mode: bool = DEFAULT_VOCU_ASYNC_MODE,
        vocu_flash_mode: bool = DEFAULT_VOCU_FLASH_MODE,
    ):
        """Save Vocu-related settings into QSettings."""
        try:
            qsettings = get_qsettings()
            qsettings.setValue("vocu_api_key", api_key)
            qsettings.setValue("vocu_voice_id", voice_id)
            qsettings.setValue("audio_mode", audio_mode)
            qsettings.setValue("max_tokens", max_tokens)
            qsettings.setValue("model", model)
            qsettings.setValue("model_type", model_type)
            qsettings.setValue("custom_model_url", custom_model_url)
            qsettings.setValue("custom_model_name", custom_model_name)
            qsettings.setValue("permanent_memory", permanent_memory)
            qsettings.setValue("preset_audio_probability", preset_audio_probability)
            qsettings.setValue("vocu_async_mode", vocu_async_mode)
            qsettings.setValue("vocu_flash_mode", vocu_flash_mode)
            qsettings.sync()
            print(
                f"Vocu 配置已保存: api_key={'*' * len(api_key) if api_key else '空'}, "
                f"voice_id={voice_id or '空'}, audio_mode={audio_mode}, max_tokens={max_tokens}, "
                f"model={model}, model_type={model_type}, preset_probability={preset_audio_probability}, "
                f"vocu_async_mode={vocu_async_mode}, vocu_flash_mode={vocu_flash_mode}"
            )
        except Exception as exc:
            print(f"保存 Vocu 配置失败: {exc}")
