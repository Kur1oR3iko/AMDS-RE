"""
聊天界面组件
"""
import random
import base64
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
    QPushButton, QLineEdit, QTextEdit, QFileDialog
)
from PyQt6.QtCore import Qt, QTimer, QSettings

from ..core import VoiceDialog, AIChatManager, VocuAudioGenerator
from ..utils import AUDIO_DIR
from ..constants import AUDIO_EMOTION_MAP, PRESET_TEXT_MAP
from .workers import ChatWorker, TypewriterWorker, PresetSelectorWorker


class ChatWidget(QWidget):
    """聊天界面组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_manager = None
        self.audio_generator = None
        self.vocu_voice_id = None
        self.current_worker = None
        self.current_streaming_text = ""
        self.permanent_memory = False
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 200);
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.chat_history)
        
        input_layout = QHBoxLayout()

        self.attach_button = QPushButton("📎")
        self.attach_button.setFixedSize(40, 40)
        self.attach_button.setStyleSheet("""
            QPushButton {
                padding: 5px;
                border-radius: 20px;
                background-color: #8B4513;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
        """)
        self.attach_button.setToolTip("上传图片")
        self.attach_button.clicked.connect(self.attach_image)
        input_layout.addWidget(self.attach_button)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("和牧濑红莉栖对话...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border-radius: 20px;
                border: 2px solid #8B4513;
                background-color: white;
                color: #333333;
                font-size: 14px;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        self.send_button = QPushButton("发送")
        self.send_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border-radius: 20px;
                background-color: #8B4513;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
        """)
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        layout.addLayout(input_layout)

        self.attached_image_path = None
    
    def init_resources(self):
        """初始化资源"""
        print("[初始化] 开始初始化资源...")
        
        qsettings = QSettings("AMDS", "Amadeus")
        model_type = qsettings.value("model_type", "默认")
        custom_model_url = qsettings.value("custom_model_url", "http://localhost:11434")
        custom_model_name = qsettings.value("custom_model_name", "")
        
        self.permanent_memory = qsettings.value("permanent_memory", False, type=bool)
        print(f"[初始化] 永久记忆功能: {'启用' if self.permanent_memory else '禁用'}")
        
        self.ai_manager = AIChatManager(model_type, custom_model_url, custom_model_name, load_history=False)
        saved_key = AIChatManager.load_api_key()
        if saved_key and model_type != "自定义":
            self.ai_manager.API_KEY = saved_key
            from openai import OpenAI
            self.ai_manager.client = OpenAI(
                base_url=self.ai_manager.BASE_URL,
                api_key=saved_key
            )
            print(f"[初始化] 已加载保存的API密钥")
        elif model_type == "自定义":
            print(f"[初始化] 使用自定义模型: {custom_model_name} at {custom_model_url}")
        
        if self.permanent_memory:
            QTimer.singleShot(1000, self.load_conversation_history)
        
        QTimer.singleShot(1500, self._init_audio_generator)
        
        print("[初始化] 基本资源初始化完成")
    
    def load_conversation_history(self):
        """延迟加载对话历史"""
        if self.ai_manager and self.permanent_memory:
            print("[延迟加载] 开始加载对话历史...")
            self.ai_manager.load_conversation()
            if self.ai_manager.conversation_history:
                print(f"[延迟加载] 显示 {len(self.ai_manager.conversation_history)} 条对话历史")
                for message in self.ai_manager.conversation_history:
                    if message["role"] == "user":
                        self.add_message("你", message["content"], "#0066CC")
                    elif message["role"] == "assistant":
                        self.add_message("牧濑红莉栖", message["content"], "#8B4513")
            print("[延迟加载] 对话历史加载完成")

    def _init_audio_generator(self):
        """初始化音频生成器"""
        qsettings = QSettings("AMDS", "Amadeus")
        
        print(f"初始化音频生成器，使用QSettings")

        try:
            vocu_api_key = qsettings.value("vocu_api_key", "")
            self.vocu_voice_id = qsettings.value("vocu_voice_id", "")
            self.audio_mode = qsettings.value("audio_mode", True, type=bool)
            self.max_tokens = qsettings.value("max_tokens", 200, type=int)
            self.preset_probability = qsettings.value("preset_probability", 30, type=int) / 100.0

            print(f"加载Vocu配置: api_key={'*' * len(vocu_api_key) if vocu_api_key else '空'}, voice_id={self.vocu_voice_id or '空'}, audio_mode={self.audio_mode}, max_tokens={self.max_tokens}, preset_probability={self.preset_probability*100}%")

            if vocu_api_key and self.audio_mode:
                self.audio_generator = VocuAudioGenerator(vocu_api_key)
                print(f"已初始化音频生成器")
            else:
                self.audio_generator = None
                if not self.audio_mode:
                    print(f"音频模式已关闭")
                else:
                    print(f"未配置Vocu API密钥，音频生成器未初始化")
        except Exception as e:
            print(f"加载音频配置失败: {e}")
            import traceback
            traceback.print_exc()
            self.audio_generator = None
            self.audio_mode = True
            self.max_tokens = 200
            self.preset_probability = 0.3

    def attach_image(self):
        """选择图片附件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.attached_image_path = file_path
            self.input_field.setPlaceholderText(f"已选择图片: {Path(file_path).name} (输入文字后发送)")
            print(f"已选择图片: {file_path}")

    def send_message(self):
        """发送消息 - 智能选择预设回复或AI生成"""
        text = self.input_field.text().strip()
        if not text and not self.attached_image_path:
            return

        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        self.attach_button.setEnabled(False)

        if self.attached_image_path:
            self.add_message_with_image("你", text or "", "#4169E1", self.attached_image_path)
        else:
            self.add_message("你", text, "#4169E1")

        matching_presets = VoiceDialog.get_all_matching_responses(text)
        has_preset = matching_presets and matching_presets != VoiceDialog.RESPONSES["default"]

        enable_audio = (self.audio_mode and
                       self.audio_generator is not None and
                       self.vocu_voice_id is not None)
        
        print(f"[音频模式] self.audio_mode={self.audio_mode}, audio_generator={self.audio_generator is not None}, vocu_voice_id={self.vocu_voice_id is not None}, enable_audio={enable_audio}")

        preset_prob = getattr(self, 'preset_probability', 0.3)
        if has_preset and random.random() < preset_prob and not self.attached_image_path and not enable_audio:
            self._use_ai_selected_preset(text, matching_presets)
        else:
            self._use_ai_response_streaming(text, self.attached_image_path, enable_audio)

        self.input_field.clear()
        self.attached_image_path = None
        self.input_field.setPlaceholderText("和牧濑红莉栖对话...")
    
    def _use_ai_selected_preset(self, user_text: str, available_presets: list):
        """使用AI智能选择预设语音"""
        self.current_worker = PresetSelectorWorker(self.ai_manager, user_text, available_presets)
        self.current_worker.preset_selected.connect(lambda preset: self._on_preset_selected(preset))
        self.current_worker.error_occurred.connect(lambda: self._on_preset_selected(random.choice(available_presets)))
        self.current_worker.start()
    
    def _on_preset_selected(self, preset_audio: str):
        """AI选择预设后的回调"""
        response_text = self.get_response_text(preset_audio)
        emotion = AUDIO_EMOTION_MAP.get(preset_audio, "normal")
        
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")
        
        self.current_worker = TypewriterWorker(response_text, emotion, char_delay=60)
        self.current_worker.char_ready.connect(self._on_streaming_char)
        self.current_worker.typing_complete.connect(self._on_preset_streaming_complete)
        self.current_worker.start()
        
        self.play_audio(preset_audio, getattr(self, 'character', None))
    
    def _use_preset_response_streaming(self, audio_name: str):
        """使用预设语音回复 - 打字机效果"""
        response_text = self.get_response_text(audio_name)
        emotion = AUDIO_EMOTION_MAP.get(audio_name, "normal")
        
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")

        self.current_worker = TypewriterWorker(response_text, emotion, char_delay=60)
        self.current_worker.char_ready.connect(self._on_streaming_char)
        self.current_worker.typing_complete.connect(self._on_preset_streaming_complete)
        self.current_worker.start()

        self.play_audio(audio_name, getattr(self, 'character', None))
    
    def _use_ai_response_streaming(self, user_text: str, image_path: str = None, enable_audio: bool = False):
        """使用AI生成回复 - 流式传输，支持图片和音频"""
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")

        voice_id = getattr(self, 'vocu_voice_id', None)
        audio_generator = getattr(self, 'audio_generator', None)
        max_tokens = getattr(self, 'max_tokens', 200)

        self.current_worker = ChatWorker(
            self.ai_manager, user_text, image_path,
            audio_generator=audio_generator,
            voice_id=voice_id,
            enable_audio=enable_audio,
            max_tokens=max_tokens
        )
        self.current_worker.emotion_ready.connect(self._on_emotion_ready)
        self.current_worker.chunk_ready.connect(self._on_streaming_chunk)
        self.current_worker.response_complete.connect(self._on_ai_streaming_complete)
        self.current_worker.error_occurred.connect(self._on_ai_error)
        self.current_worker.audio_status.connect(self._on_audio_status)
        self.current_worker.audio_ready.connect(self._on_audio_ready)
        self.current_worker.japanese_text_ready.connect(self._on_japanese_text_ready)
        self.current_worker.start()
    
    def _append_streaming_prefix(self, sender: str, color: str, show_loading: bool = True):
        """添加流式消息的前缀"""
        self.chat_history.append(
            f'<span style="color: {color}; font-weight: bold;">{sender}:</span> '
        )
        self._streaming_block = self.chat_history.document().lastBlock()
        self._streaming_pos = len(self._streaming_block.text())

        if show_loading:
            self._loading_dots = 0
            self._loading_timer = QTimer(self)
            self._loading_timer.timeout.connect(self._update_loading_animation)
            self._loading_timer.start(500)
            self._loading_active = True

    def _update_loading_animation(self):
        """更新加载动画"""
        if not hasattr(self, '_loading_active') or not self._loading_active:
            return

        self._loading_dots = (self._loading_dots % 3) + 1
        dots = "." * self._loading_dots

        cursor = self.chat_history.textCursor()

        if hasattr(self, '_loading_start_pos') and hasattr(self, '_loading_end_pos'):
            cursor.setPosition(self._loading_start_pos)
            cursor.setPosition(self._loading_end_pos, cursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

        cursor.movePosition(cursor.MoveOperation.End)
        self._loading_start_pos = cursor.position()
        cursor.insertHtml(f'<span style="color: #888;">{dots}</span>')
        self._loading_end_pos = cursor.position()

        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _stop_loading_animation(self):
        """停止加载动画并清除加载点"""
        if hasattr(self, '_loading_timer') and self._loading_timer:
            self._loading_timer.stop()

        if hasattr(self, '_loading_active') and self._loading_active:
            if hasattr(self, '_loading_start_pos') and hasattr(self, '_loading_end_pos'):
                cursor = self.chat_history.textCursor()
                cursor.setPosition(self._loading_start_pos)
                cursor.setPosition(self._loading_end_pos, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()

        self._loading_active = False
        self._loading_dots = 0
        if hasattr(self, '_loading_start_pos'):
            delattr(self, '_loading_start_pos')
        if hasattr(self, '_loading_end_pos'):
            delattr(self, '_loading_end_pos')

    def _on_streaming_char(self, char: str):
        """打字机效果 - 接收单个字符"""
        if hasattr(self, '_loading_active') and self._loading_active:
            self._stop_loading_animation()

        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if not self.current_streaming_text:
            cursor.insertHtml("&nbsp;")

        self.current_streaming_text += char
        char_escaped = char.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        cursor.insertHtml(f'<span style="color: #000000;">{char_escaped}</span>')

        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_streaming_chunk(self, chunk: str):
        """流式传输 - 接收文本片段"""
        if hasattr(self, '_loading_active') and self._loading_active:
            self._stop_loading_animation()

        if chunk.startswith("[日语]"):
            japanese_text = chunk[4:].strip()
            print(f"[流式传输] 检测到日语文本: {japanese_text}")
            self._on_japanese_text_ready(japanese_text)
            return

        if '[' in chunk and ']' in chunk:
            import re
            match = re.search(r'\[([^\]]+)\]', chunk)
            if match:
                emotion = match.group(1)
                print(f"[流式传输] 检测到表情标签: {emotion}")
                self._on_emotion_ready(emotion)
                chunk = re.sub(r'^\[[^\]]+\]', '', chunk).strip()
                if not chunk:
                    return

        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        if not self.current_streaming_text:
            cursor.insertHtml("&nbsp;")

        self.current_streaming_text += chunk
        chunk_escaped = chunk.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        cursor.insertHtml(f'<span style="color: #000000;">{chunk_escaped}</span>')

        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_preset_streaming_complete(self, full_text: str, emotion: str):
        """预设回答打字机效果完成"""
        if hasattr(self, 'character') and self.character:
            self.character.set_emotion(emotion)

        if hasattr(self, 'ai_manager') and self.ai_manager:
            self.ai_manager.conversation_history.append({"role": "assistant", "content": full_text})

        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.attach_button.setEnabled(True)
        self.input_field.setFocus()

        self.current_streaming_text = ""
    
    def _on_emotion_ready(self, emotion: str):
        """表情已确定，立即切换"""
        print(f"[表情] _on_emotion_ready 被调用，表情: {emotion}")
        if hasattr(self, 'character') and self.character:
            print(f"[表情] character存在，设置表情")
            self.character.set_emotion(emotion)
        else:
            print(f"[表情] character不存在")

    def _on_audio_status(self, status: str):
        """音频生成状态更新"""
        print(f"[音频状态] {status}")

    def _on_audio_ready(self, audio_source: str):
        """音频准备好，开始播放"""
        print(f"[音频播放] _on_audio_ready 被调用，音频源: {audio_source}")
        if audio_source:
            if audio_source.startswith('http://') or audio_source.startswith('https://'):
                print(f"[音频播放] 检测到URL，直接播放")
            else:
                print(f"[音频播放] 检测到本地文件，检查文件是否存在: {Path(audio_source).exists()}")
            self.play_vocu_audio(audio_source)
        else:
            print(f"[音频播放] 音频源为空")

    def _on_playback_state_changed(self, state):
        """播放状态变化时处理"""
        from PyQt6.QtMultimedia import QMediaPlayer
        print(f"[播放状态] 状态变化: {state}, PlayingState: {QMediaPlayer.PlaybackState.PlayingState}")
        
        if state == QMediaPlayer.PlaybackState.PlayingState:
            if hasattr(self, 'character') and self.character and not self.character.is_speaking:
                print(f"[表情] 音频开始播放，启动说话动画")
                self.character.start_speaking()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            if hasattr(self, 'character') and self.character and self.character.is_speaking:
                print(f"[表情] 音频停止播放，停止说话动画")
                self.character.stop_speaking()

    def _on_japanese_text_ready(self, japanese_text: str):
        """日语文本准备好，显示在人物下方"""
        print(f"[调试] _on_japanese_text_ready 被调用, 日语文本: {japanese_text}")
        print(f"[调试] hasattr(self, 'character')={hasattr(self, 'character')}, hasattr(self, 'audio_mode')={hasattr(self, 'audio_mode')}")
        if hasattr(self, 'audio_mode'):
            print(f"[调试] self.audio_mode={self.audio_mode}")
        
        if hasattr(self, 'character') and self.character:
            self.character.set_japanese_text(japanese_text, append=False)
            
            print(f"[音频模式检查] hasattr(self, 'audio_mode')={hasattr(self, 'audio_mode')}, self.audio_mode={getattr(self, 'audio_mode', 'N/A')}")
            
            if hasattr(self, 'audio_mode') and not self.audio_mode:
                print(f"[表情] 非音频模式，启动说话动画")
                try:
                    self.character.start_speaking()
                    
                    duration = 3000
                    print(f"[表情] 说话动画持续时间: {duration}ms")
                    
                    def stop_speaking():
                        print(f"[表情] 停止说话动画")
                        if hasattr(self, 'character') and self.character:
                            self.character.stop_speaking()
                    QTimer.singleShot(duration, stop_speaking)
                except Exception as e:
                    print(f"[表情] 非音频模式说话动画异常: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[表情] 音频模式，不启动说话动画")

    def _on_ai_streaming_complete(self, full_text: str, emotion: str, audio_path: str = ""):
        """AI流式传输完成"""

        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.attach_button.setEnabled(True)
        self.input_field.setFocus()

        self.current_streaming_text = ""
        
        if self.permanent_memory and self.ai_manager:
            self.ai_manager.save_conversation()

    def _on_ai_error(self, error_msg: str):
        """AI调用出错时的回调"""
        if error_msg == "timeout":
            timeout_message = "不好意思，我想我这边网络有点问题，我们稍后再聊这个话题吧"
            self.current_streaming_text += f"\n{timeout_message}"
        else:
            self.current_streaming_text += f"\n[错误: {error_msg}]"
        
        try:
            cursor = self.chat_history.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            error_escaped = self.current_streaming_text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            cursor.insertHtml(f'<span style="color: #FF0000;">{error_escaped}</span>')
            scrollbar = self.chat_history.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            print(f"更新错误显示失败: {e}")

        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.attach_button.setEnabled(True)
        self.input_field.setFocus()
    
    def add_message(self, sender: str, text: str, color: str):
        """添加完整消息到历史"""
        self.chat_history.append(
            f'<span style="color: {color}; font-weight: bold;">{sender}:</span> '
            f'<span style="color: #000000;">{text}</span>'
        )
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def add_message_with_image(self, sender: str, text: str, color: str, image_path: str):
        """添加带图片的消息到历史"""
        with open(image_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()

        ext = Path(image_path).suffix.lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.bmp': 'image/bmp',
            '.gif': 'image/gif'
        }.get(ext, 'image/png')

        html = f'<span style="color: {color}; font-weight: bold;">{sender}:</span>'
        if text:
            html += f' <span style="color: #000000;">{text}</span>'
        html += f'<br><img src="data:{mime_type};base64,{img_data}" style="max-width: 200px; max-height: 150px; border-radius: 5px; margin-top: 5px;">'

        self.chat_history.append(html)
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def get_response_text(self, audio_name: str) -> str:
        """根据音频文件名获取对应的文本"""
        return PRESET_TEXT_MAP.get(audio_name, audio_name)
    
    def play_audio(self, audio_name: str, character=None):
        """播放预设音频"""
        from ..core import AudioPlayer
        audio_path = AUDIO_DIR / f"{audio_name}.ogg"
        print(f"[音频] play_audio 被调用, 音频: {audio_name}, 路径: {audio_path}")
        if audio_path.exists():
            print(f"[音频] 音频文件存在，创建播放器")
            self.audio_player = AudioPlayer(audio_path)
            if character:
                print(f"[音频] 连接音频信号到角色动画")
                self.audio_player.started.connect(character.start_speaking)
                self.audio_player.finished.connect(character.stop_speaking)
            print(f"[音频] 开始播放")
            self.audio_player.start()
        else:
            print(f"[音频] 音频文件不存在: {audio_path}")
    
    def play_vocu_audio(self, audio_source: str):
        """播放Vocu生成的音频（URL或本地文件）"""
        from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
        from PyQt6.QtCore import QUrl
        
        print(f"[Vocu音频] play_vocu_audio 被调用, 音频源: {audio_source}")
        
        if not hasattr(self, 'media_player'):
            self.media_player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.media_player.setAudioOutput(self.audio_output)
            self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
            print(f"[Vocu音频] 创建新的媒体播放器")
        
        if audio_source.startswith('http://') or audio_source.startswith('https://'):
            print(f"[Vocu音频] 播放URL: {audio_source}")
            self.media_player.setSource(QUrl(audio_source))
        else:
            print(f"[Vocu音频] 播放本地文件: {audio_source}")
            self.media_player.setSource(QUrl.fromLocalFile(audio_source))
        
        self.media_player.play()
        print(f"[Vocu音频] 开始播放")
