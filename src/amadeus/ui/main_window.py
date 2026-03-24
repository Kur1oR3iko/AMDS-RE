"""
主窗口模块
"""
import sys
import os
import json
import threading
from pathlib import Path

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMessageBox, QDialog, QApplication
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

from ..core import VoiceDialog, AIChatManager, AudioPlayer
from ..utils import IMAGES_DIR, AUDIO_DIR, get_config_manager
from .character_widget import KurisuCharacter
from .chat_widget import ChatWidget
from .settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amadeus - 牧濑红莉栖")
        self.setMinimumSize(900, 600)
        
        icon_path = IMAGES_DIR / "ic_launcher.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2C1810;
            }
        """)
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.character = KurisuCharacter()
        left_layout.addWidget(self.character, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(left_panel, 1)
        
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.logo_label = QLabel()
        logo_pixmap = QPixmap(str(IMAGES_DIR / "logo1.png"))
        if not logo_pixmap.isNull():
            scaled_logo = logo_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(scaled_logo)
        title_layout.addWidget(self.logo_label)

        title = QLabel("Amadeus System")
        title.setStyleSheet("""
            QLabel {
                color: #D2691E;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        title_layout.addWidget(title)

        self.settings_button = QPushButton()
        settings_pixmap = QPixmap(str(IMAGES_DIR / "logo39.png"))
        if not settings_pixmap.isNull():
            scaled_pixmap = settings_pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            settings_icon = QIcon(scaled_pixmap)
            self.settings_button.setIcon(settings_icon)
            self.settings_button.setIconSize(scaled_pixmap.size())
        self.settings_button.setFixedSize(120, 120)
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(139, 69, 19, 0.3);
                border-radius: 5px;
            }
        """)
        self.settings_button.setToolTip("设置")
        self.settings_button.clicked.connect(self.open_settings)
        title_layout.addWidget(self.settings_button)

        right_layout.addWidget(title_widget)
        
        self.chat = ChatWidget()
        self.chat.character = self.character
        right_layout.addWidget(self.chat, 1)
        
        main_layout.addWidget(right_panel, 2)
    
    def play_tone(self):
        """播放启动音效 tone.ogg"""
        print("[启动] 开始播放启动音效...")
        tone_path = AUDIO_DIR / "tone.ogg"
        print(f"[启动] 启动音效路径: {tone_path}")
        print(f"[启动] 启动音效文件存在: {tone_path.exists()}")
        if tone_path.exists():
            print("[启动] 创建AudioPlayer实例...")
            self.tone_player = AudioPlayer(tone_path)
            print("[启动] 连接完成信号...")
            self.tone_player.finished.connect(self.play_greeting)
            print("[启动] 开始播放启动音效...")
            self.tone_player.start()
        else:
            print("[启动] 启动音效文件不存在")

    def play_greeting(self):
        """播放问候语 - 带动画和聊天显示"""
        print("[启动] 开始播放问候语...")
        if self.chat.permanent_memory:
            print("[启动] 永久记忆功能已启用，跳过欢迎语")
            return
        
        print("[启动] 获取随机问候语...")
        greeting = VoiceDialog.get_random_greeting()
        print(f"[启动] 随机问候语: {greeting}")

        print("[启动] 获取问候语文本...")
        greeting_text = self.chat.get_response_text(greeting)
        print(f"[启动] 问候语文本: {greeting_text}")
        self.chat.add_message("牧濑红莉栖", greeting_text, "#8B4513")

        audio_path = AUDIO_DIR / f"{greeting}.ogg"
        print(f"[启动] 问候语音频路径: {audio_path}")
        print(f"[启动] 问候语音频文件存在: {audio_path.exists()}")
        if audio_path.exists():
            print("[启动] 获取表情...")
            emotion = VoiceDialog.get_emotion_for_audio(greeting)
            print(f"[启动] 表情: {emotion}")
            self.character.set_emotion(emotion)
            print("[启动] 播放音频...")
            self.chat.play_audio(greeting, self.character)
        else:
            print("[启动] 问候语音频文件不存在")

    def open_settings(self):
        """打开设置对话框"""
        from PyQt6.QtCore import QSettings
        from openai import OpenAI
        
        qsettings = QSettings("AMDS", "Amadeus")
        
        current_api_key = self._load_api_key()
        current_model = qsettings.value("model", "doubao-seed-2-0-lite-260215")
        current_model_type = qsettings.value("model_type", "默认")
        current_custom_url = qsettings.value("custom_model_url", "http://localhost:11434")
        current_custom_name = qsettings.value("custom_model_name", "")
        vocu_api_key = qsettings.value("vocu_api_key", "")
        vocu_voice_id = qsettings.value("vocu_voice_id", "")
        audio_mode = qsettings.value("audio_mode", True, type=bool)
        max_tokens = qsettings.value("max_tokens", 200, type=int)
        preset_probability = qsettings.value("preset_probability", 30, type=int)
        async_audio = qsettings.value("async_audio_generation", False, type=bool)

        print(f"加载Vocu设置: api_key={'*' * len(vocu_api_key) if vocu_api_key else '空'}, voice_id={vocu_voice_id or '空'}, audio_mode={audio_mode}, max_tokens={max_tokens}, preset_probability={preset_probability}, async_audio={async_audio}")

        dialog = SettingsDialog(self, current_api_key, vocu_api_key, vocu_voice_id, audio_mode, max_tokens,
                                current_model, current_model_type, current_custom_url, current_custom_name,
                                preset_probability, async_audio)
        result = dialog.exec()
        print(f"设置对话框结果: {result}, Accepted={QDialog.DialogCode.Accepted}")

        if result == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            print(f"获取设置: api_key={'*' * len(settings['api_key']) if settings['api_key'] else '空'}, vocu_api_key={'*' * len(settings['vocu_api_key']) if settings['vocu_api_key'] else '空'}, vocu_voice_id={settings['vocu_voice_id'] or '空'}, audio_mode={settings['audio_mode']}, max_tokens={settings['max_tokens']}")

            if settings["api_key"]:
                self.chat.ai_manager.API_KEY = settings["api_key"]
                self._save_api_key(settings["api_key"])

            self.chat.ai_manager.MODEL = settings["model"]
            print(f"模型已更新为: {settings['model']}")

            if settings["model_type"] == "自定义":
                current_history = self.chat.ai_manager.conversation_history if hasattr(self.chat.ai_manager, 'conversation_history') else []
                self.chat.ai_manager = AIChatManager(
                    model_type=settings["model_type"],
                    custom_model_url=settings["custom_model_url"],
                    custom_model_name=settings["custom_model_name"]
                )
                self.chat.ai_manager.conversation_history = current_history
                print(f"[设置] 已切换到自定义模型: {settings['custom_model_name']} at {settings['custom_model_url']}")
            else:
                self.chat.ai_manager.client = OpenAI(
                    base_url=self.chat.ai_manager.BASE_URL,
                    api_key=self.chat.ai_manager.API_KEY
                )
                print(f"[设置] 已切换到默认模型: {settings['model']}")

            old_permanent_memory = self.chat.permanent_memory
            new_permanent_memory = settings.get("permanent_memory", False)
            
            print(f"保存Vocu设置...")
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
                settings["preset_probability"],
                settings.get("async_audio_generation", False)
            )
            
            self.chat.permanent_memory = new_permanent_memory
            if self.chat.ai_manager:
                self.chat.ai_manager.permanent_memory = new_permanent_memory
            
            if old_permanent_memory and not new_permanent_memory:
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("确认关闭永久记忆")
                msg_box.setText("你之前所说的背负所有人的记忆，就是这么一回事吗？")
                
                confirm_button = msg_box.addButton("。。。", QMessageBox.ButtonRole.AcceptRole)
                cancel_button = msg_box.addButton("我不关闭了", QMessageBox.ButtonRole.RejectRole)
                
                msg_box.exec()
                
                if msg_box.clickedButton() == confirm_button:
                    print("永久记忆功能已关闭，正在清除对话历史...")
                    if self.chat.ai_manager:
                        self.chat.ai_manager.clear_history()
                    print("正在重启软件...")
                    from PyQt6.QtWidgets import QApplication
                    QApplication.instance().quit()
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                else:
                    print("用户取消关闭永久记忆")
                    new_permanent_memory = True
                    self.chat.permanent_memory = new_permanent_memory
                    if self.chat.ai_manager:
                        self.chat.ai_manager.permanent_memory = new_permanent_memory
                    self._save_vocu_settings(
                        settings["vocu_api_key"], 
                        settings["vocu_voice_id"], 
                        settings["audio_mode"], 
                        settings["max_tokens"], 
                        settings["model"], 
                        settings["model_type"], 
                        settings["custom_model_url"], 
                        settings["custom_model_name"],
                        new_permanent_memory
                    )
            elif not old_permanent_memory and new_permanent_memory:
                print("永久记忆功能已开启，正在加载对话历史...")
                if self.chat.ai_manager:
                    self.chat.ai_manager.load_conversation()
            
            self.chat._init_audio_generator()

            print(f"设置已更新: API密钥已{'保存' if settings['api_key'] else '清空'}")

    def _save_api_key(self, api_key: str):
        """保存API密钥到本地文件"""
        try:
            config_dir = Path.home() / ".amadeus"
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / "config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump({"api_key": api_key}, f)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def _load_api_key(self) -> str:
        """从本地文件加载API密钥"""
        try:
            config_file = Path.home() / ".amadeus" / "config.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get("api_key", "")
        except Exception as e:
            print(f"加载配置失败: {e}")
        return ""

    def _save_vocu_settings(self, api_key: str, voice_id: str, audio_mode: bool = True,
                            max_tokens: int = 500, model: str = "doubao-seed-2-0-lite-260215",
                            model_type: str = "默认", custom_model_url: str = "http://localhost:11434",
                            custom_model_name: str = "", permanent_memory: bool = False,
                            preset_probability: int = 30, async_audio: bool = False):
        """保存Vocu设置到QSettings"""
        from PyQt6.QtCore import QSettings

        try:
            qsettings = QSettings("AMDS", "Amadeus")

            qsettings.setValue("vocu_api_key", api_key)
            qsettings.setValue("vocu_voice_id", voice_id)
            qsettings.setValue("audio_mode", audio_mode)
            qsettings.setValue("max_tokens", max_tokens)
            qsettings.setValue("model", model)
            qsettings.setValue("model_type", model_type)
            qsettings.setValue("custom_model_url", custom_model_url)
            qsettings.setValue("custom_model_name", custom_model_name)
            qsettings.setValue("permanent_memory", permanent_memory)
            qsettings.setValue("preset_probability", preset_probability)
            qsettings.setValue("async_audio_generation", async_audio)

            qsettings.sync()

            config_manager = get_config_manager()
            config_manager.set("max_tokens", max_tokens)
            config_manager.set("preset_probability", preset_probability / 100.0)
            config_manager.set("async_audio_generation", async_audio)
            config_manager.save()

            print(f"Vocu配置已保存: api_key={'*' * len(api_key) if api_key else '空'}, voice_id={voice_id or '空'}, audio_mode={audio_mode}, max_tokens={max_tokens}, model={model}, model_type={model_type}, preset_probability={preset_probability}%, async_audio={async_audio}")
        except Exception as e:
            print(f"保存Vocu配置失败: {e}")
            import traceback
            traceback.print_exc()


class SplashScreen(QMainWindow):
    """启动动画窗口 - 使用Logo序列"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Amadeus")
        self.setFixedSize(250, 300)
        self.setStyleSheet("background-color: #1a1a2e;")
        
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo_label)
        
        self.loading_text = QLabel("Loading Amadeus System...")
        self.loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_text.setStyleSheet("""
            QLabel {
                color: #D2691E;
                font-size: 16px;
                font-weight: bold;
                margin-top: 20px;
            }
        """)
        layout.addWidget(self.loading_text)
        
        version = QLabel("v0.2.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("""
            QLabel {
                color: #8B4513;
                font-size: 12px;
                margin-top: 10px;
            }
        """)
        layout.addWidget(version)
        
        self.current_frame = 1
        self.total_frames = 39
        self.animation_speed = 80
        
        self.start_animation()

    def start_animation(self):
        """开始Logo动画"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(self.animation_speed)
        self.update_frame()
    
    def update_frame(self):
        """更新动画帧"""
        logo_path = IMAGES_DIR / f"logo{self.current_frame}.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.logo_label.setPixmap(scaled)
        
        self.current_frame += 1
        if self.current_frame > self.total_frames:
            self.current_frame = 1
    
    def stop_animation(self):
        """停止动画"""
        if hasattr(self, 'timer'):
            self.timer.stop()


def main():
    """主入口函数"""
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication(sys.argv)
    
    app.setStyle("Fusion")
    
    splash = SplashScreen()
    splash.show()
    
    window = MainWindow()
    
    def init_resources():
        print("[启动] 开始异步初始化资源...")
        window.chat.init_resources()
        print("[启动] 资源初始化完成")
    
    init_thread = threading.Thread(target=init_resources, daemon=True)
    init_thread.start()
    
    def show_main_window():
        splash.stop_animation()
        splash.close()
        window.show()
        window.play_tone()
    
    QTimer.singleShot(2500, show_main_window)
    
    sys.exit(app.exec())
