"""Chat panel widget and audio playback coordination."""

import random
from pathlib import Path

from PyQt6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QTextEdit, QVBoxLayout, QWidget
from PyQt6.QtCore import QThread, QTimer, QUrl, pyqtSignal
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer

from core.app_config import DEFAULT_MODEL, DEFAULT_PRESET_AUDIO_PROBABILITY, DEFAULT_VOCU_ASYNC_MODE, DEFAULT_VOCU_FLASH_MODE, LEGACY_MODEL_MAP, MODEL_OPTIONS
from core.reply_parser import clean_stream_display_text, extract_emotions, history_content_to_text
from core.resources import AUDIO_DIR, get_qsettings
from services.ai_manager import AIChatManager
from services.audio_player import AudioPlayer, NetworkStreamPlayer
from services.voice_dialog import VoiceDialog
from services.workers import ChatWorker, TypewriterWorker
from utils.image_utils import to_data_url

class ChatWidget(QWidget):
    """聊天界面组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_manager = None  # 延迟初始化
        self.audio_generator = None  # 延迟初始化
        self.vocu_voice_id = None
        self.audio_available = False
        self.current_worker = None  # 当前工作线程
        self.current_streaming_text = ""  # 当前流式显示的文本
        self.permanent_memory = False  # 永久记忆功能
        self._chat_request_active = False
        self._response_started = False
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 聊天历史显示区
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
        
        # 输入区域
        input_layout = QHBoxLayout()

        # 附件按钮
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

        # 当前附加的图片
        self.attached_image_path = None
        self._request_watchdog = QTimer(self)
        self._request_watchdog.setSingleShot(True)
        self._request_watchdog.timeout.connect(self._handle_request_watchdog_timeout)
    
    def init_resources(self):
        """初始化资源（异步调用）"""
        print("[初始化] 开始初始化资源...")
        
        # 加载模型设置
        qsettings = get_qsettings()
        model_type = qsettings.value("model_type", "默认")
        saved_model = LEGACY_MODEL_MAP.get(qsettings.value("model", DEFAULT_MODEL), qsettings.value("model", DEFAULT_MODEL))
        if saved_model not in MODEL_OPTIONS:
            saved_model = DEFAULT_MODEL
        AIChatManager.MODEL = saved_model
        custom_model_url = qsettings.value("custom_model_url", "http://localhost:11434")
        custom_model_name = qsettings.value("custom_model_name", "")
        
        # 加载永久记忆设置
        self.permanent_memory = qsettings.value("permanent_memory", False, type=bool)
        print(f"[初始化] 永久记忆功能: {'启用' if self.permanent_memory else '禁用'}")
        
        # 初始化AI管理器（不加载历史，延迟加载）
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
        
        # 延迟加载对话历史（主窗口显示后）
        if self.permanent_memory:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, self.load_conversation_history)
        
        # 延迟初始化音频生成器（主窗口显示后）
        from PyQt6.QtCore import QTimer
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
                        self.add_message("你", history_content_to_text(message["content"]), "#0066CC")
                    elif message["role"] == "assistant":
                        self.add_message("牧濑红莉栖", history_content_to_text(message["content"]), "#8B4513")
            print("[延迟加载] 对话历史加载完成")

    def _init_audio_generator(self):
        """初始化音频生成器"""
        # 使用QSettings加载Vocu设置
        qsettings = get_qsettings()
        self.audio_available = False
        
        print(f"初始化音频生成器，使用QSettings")

        try:
            vocu_api_key = (qsettings.value("vocu_api_key", "") or "").strip()
            self.vocu_voice_id = (qsettings.value("vocu_voice_id", "") or "").strip()
            self.audio_mode = qsettings.value("audio_mode", True, type=bool)
            self.max_tokens = qsettings.value("max_tokens", 200, type=int)
            self.preset_audio_probability = qsettings.value("preset_audio_probability", DEFAULT_PRESET_AUDIO_PROBABILITY, type=int)
            self.vocu_async_mode = qsettings.value("vocu_async_mode", DEFAULT_VOCU_ASYNC_MODE, type=bool)
            self.vocu_flash_mode = qsettings.value("vocu_flash_mode", DEFAULT_VOCU_FLASH_MODE, type=bool)

            print(f"加载Vocu配置: api_key={'*' * len(vocu_api_key) if vocu_api_key else '空'}, voice_id={self.vocu_voice_id or '空'}, audio_mode={self.audio_mode}, max_tokens={self.max_tokens}, preset_probability={self.preset_audio_probability}, vocu_async_mode={self.vocu_async_mode}, vocu_flash_mode={self.vocu_flash_mode}")

            # 音频模式关闭时直接不创建生成器，后面发送消息会自然走文本分支
            if vocu_api_key and self.audio_mode and self.vocu_voice_id:
                from services.audiogenerate import VocuAudioGenerator
                self.audio_generator = VocuAudioGenerator(vocu_api_key)
                self.audio_available = True
                print(f"已初始化音频生成器")
            else:
                self.audio_generator = None
                if not self.audio_mode:
                    print(f"音频模式已关闭")
                elif not self.vocu_voice_id:
                    print(f"未配置Vocu声音ID，音频生成器未初始化")
                else:
                    print(f"未配置Vocu API密钥，音频生成器未初始化")
        except Exception as e:
            print(f"加载音频配置失败: {e}")
            import traceback
            traceback.print_exc()
            # 设置默认值
            self.audio_generator = None
            self.audio_available = False
            self.audio_mode = True
            self.max_tokens = 200
            self.preset_audio_probability = DEFAULT_PRESET_AUDIO_PROBABILITY
            self.vocu_async_mode = DEFAULT_VOCU_ASYNC_MODE
            self.vocu_flash_mode = DEFAULT_VOCU_FLASH_MODE

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
            # 在输入框显示提示
            self.input_field.setPlaceholderText(f"已选择图片: {Path(file_path).name} (输入文字后发送)")
            print(f"已选择图片: {file_path}")

    def send_message(self):
        """发送消息 - 智能选择预设回复或AI生成"""
        text = self.input_field.text().strip()
        if not text and not self.attached_image_path:
            return

        self._set_input_controls_enabled(False, "send_message")

        # 显示用户消息（包含图片）
        # 先显示给用户看，再把简化后的文本写入内部历史，避免 base64 污染记忆
        if self.attached_image_path:
            self.add_message_with_image("你", text or "", "#4169E1", self.attached_image_path)
        else:
            self.add_message("你", text, "#4169E1")

        # 获取所有匹配的预设语音
        matching_presets = VoiceDialog.get_all_matching_responses(text)
        has_preset = matching_presets and matching_presets != VoiceDialog.RESPONSES["default"]

        # 判断是否启用音频生成
        enable_audio = bool(
            self.audio_mode
            and self.audio_generator is not None
            and self.vocu_voice_id
        )
        self.audio_available = enable_audio
        
        print(f"[音频模式] self.audio_mode={self.audio_mode}, audio_generator={self.audio_generator is not None}, vocu_voice_id={bool(self.vocu_voice_id)}, enable_audio={enable_audio}")

        # 滑块保存的是 0~100 的整数，这里先换成真正的概率值再比较
        preset_probability = max(0, min(100, getattr(self, "preset_audio_probability", DEFAULT_PRESET_AUDIO_PROBABILITY))) / 100

        # 按设置概率使用预设，剩余概率使用AI生成（有图片或启用音频时不使用预设）
        if has_preset and random.random() < preset_probability and not self.attached_image_path and not enable_audio:
            # 使用AI智能选择最佳预设
            self._use_ai_selected_preset(text, matching_presets)
        else:
            # 使用AI生成回复 - 流式传输
            self._use_ai_response_streaming(text, self.attached_image_path, enable_audio)

        # 清空输入和附件
        self.input_field.clear()
        self.attached_image_path = None
        self.input_field.setPlaceholderText("和牧濑红莉栖对话...")
    
    def _use_ai_selected_preset(self, user_text: str, available_presets: list):
        """使用AI智能选择预设语音"""
        # 在后台线程中选择预设
        class PresetSelectorWorker(QThread):
            preset_selected = pyqtSignal(str)  # 选中的预设
            error_occurred = pyqtSignal()
            
            def __init__(self, ai_manager, user_text, presets):
                super().__init__()
                self.ai_manager = ai_manager
                self.user_text = user_text
                self.presets = presets
            
            def run(self):
                try:
                    selected = self.ai_manager.select_best_preset(self.user_text, self.presets)
                    self.preset_selected.emit(selected)
                except:
                    self.error_occurred.emit()
        
        self.current_worker = PresetSelectorWorker(self.ai_manager, user_text, available_presets)
        self.current_worker.preset_selected.connect(lambda preset: self._on_preset_selected(preset))
        self.current_worker.error_occurred.connect(lambda: self._on_preset_selected(random.choice(available_presets)))
        self.current_worker.start()
    
    def _on_preset_selected(self, preset_audio: str):
        """AI选择预设后的回调"""
        # 使用打字机效果显示
        response_text = self.get_response_text(preset_audio)
        emotion = VoiceDialog.get_emotion_for_audio(preset_audio)
        
        # 先添加空的消息占位
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")
        
        # 创建打字机效果线程
        self.current_worker = TypewriterWorker(response_text, emotion, char_delay=60)
        self.current_worker.char_ready.connect(self._on_streaming_char)
        self.current_worker.typing_complete.connect(self._on_preset_streaming_complete)
        self.current_worker.start()
        
        # 播放音频
        self.play_audio(preset_audio, getattr(self, 'character', None))
    
    def _use_preset_response_streaming(self, audio_name: str):
        """使用预设语音回复 - 打字机效果"""
        response_text = self.get_response_text(audio_name)
        emotion = VoiceDialog.get_emotion_for_audio(audio_name)
        
        # 先添加空的消息占位
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")

        # 创建打字机效果线程
        self.current_worker = TypewriterWorker(response_text, emotion, char_delay=60)
        self.current_worker.char_ready.connect(self._on_streaming_char)
        self.current_worker.typing_complete.connect(self._on_preset_streaming_complete)
        self.current_worker.start()

        # 播放音频
        self.play_audio(audio_name, getattr(self, 'character', None))
    
    def _use_ai_response_streaming(self, user_text: str, image_path: str = None, enable_audio: bool = False):
        """使用AI生成回复 - 流式传输，支持图片和音频"""
        # 先添加空的消息占位
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")

        # 创建流式API线程 - 支持图片和音频
        voice_id = getattr(self, 'vocu_voice_id', None)
        audio_generator = getattr(self, 'audio_generator', None)
        max_tokens = getattr(self, 'max_tokens', 200)
        vocu_async_mode = getattr(self, 'vocu_async_mode', DEFAULT_VOCU_ASYNC_MODE)
        vocu_flash_mode = getattr(self, 'vocu_flash_mode', DEFAULT_VOCU_FLASH_MODE)

        self.current_worker = ChatWorker(
            self.ai_manager, user_text, image_path,
            audio_generator=audio_generator,
            voice_id=voice_id,
            enable_audio=enable_audio,
            max_tokens=max_tokens,
            vocu_async_mode=vocu_async_mode,
            vocu_flash_mode=vocu_flash_mode
        )
        self.current_worker.emotion_ready.connect(self._on_emotion_ready)
        self.current_worker.chunk_ready.connect(self._on_streaming_chunk)
        self.current_worker.response_complete.connect(self._on_ai_streaming_complete)
        self.current_worker.error_occurred.connect(self._on_ai_error)
        self.current_worker.audio_status.connect(self._on_audio_status)
        self.current_worker.audio_ready.connect(self._on_audio_ready)
        self.current_worker.japanese_text_ready.connect(self._on_japanese_text_ready)
        self.current_worker.finished.connect(self._restore_input_controls)
        self.current_worker.start()
    
    def _append_streaming_prefix(self, sender: str, color: str, show_loading: bool = True):
        """添加流式消息的前缀 - 使用文本块方式，可选加载动画"""
        # 添加发送者前缀，不换行
        self.chat_history.append(
            f'<span style="color: {color}; font-weight: bold;">{sender}:</span> '
        )
        # 保存当前块位置用于后续追加
        self._streaming_block = self.chat_history.document().lastBlock()
        self._streaming_pos = len(self._streaming_block.text())

        # 启动加载动画
        if show_loading:
            self._loading_dots = 0
            self._loading_timer = QTimer(self)
            self._loading_timer.timeout.connect(self._update_loading_animation)
            self._loading_timer.start(500)  # 每500ms更新一次
            self._loading_active = True

    def _kick_request_watchdog(self, reason: str, timeout_ms: int = 3500):
        """只要请求仍在进行，就在每次收到有效进展时重置静默看门狗。"""
        if not self._chat_request_active:
            return
        self._request_watchdog.start(timeout_ms)
        print(f"[输入] 重置静默看门狗，reason={reason}, timeout_ms={timeout_ms}")

    def _handle_request_watchdog_timeout(self):
        """上游流式结束信号偶发丢失时，避免输入框一直卡死。"""
        if not self._chat_request_active:
            return
        if not self._response_started:
            print("[输入] 静默看门狗触发，但尚未收到回复内容，继续等待。")
            self._kick_request_watchdog("watchdog_waiting_for_first_response", 3500)
            return
        print("[输入] 静默看门狗触发，未收到结束信号，执行兜底恢复。")
        self._restore_input_controls()

    def _update_loading_animation(self):
        """更新加载动画（三个点循环）- 使用QTextCursor精确定位"""
        if not hasattr(self, '_loading_active') or not self._loading_active:
            return

        # 更新点的数量 (1 -> 2 -> 3 -> 1...)
        self._loading_dots = (self._loading_dots % 3) + 1
        dots = "." * self._loading_dots

        cursor = self.chat_history.textCursor()

        # 删除之前的加载点
        if hasattr(self, '_loading_start_pos') and hasattr(self, '_loading_end_pos'):
            cursor.setPosition(self._loading_start_pos)
            cursor.setPosition(self._loading_end_pos, cursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

        # 在末尾插入新的加载点
        cursor.movePosition(cursor.MoveOperation.End)
        self._loading_start_pos = cursor.position()
        cursor.insertHtml(f'<span style="color: #888;">{dots}</span>')
        self._loading_end_pos = cursor.position()

        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _stop_loading_animation(self):
        """停止加载动画并清除加载点"""
        if hasattr(self, '_loading_timer') and self._loading_timer:
            self._loading_timer.stop()

        # 清除已显示的加载点
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
        self._response_started = True
        self._kick_request_watchdog("streaming_char")
        # 停止加载动画
        if hasattr(self, '_loading_active') and self._loading_active:
            self._stop_loading_animation()

        # 使用 QTextCursor 插入带颜色的字符
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        # 如果是第一个字符，先插入空格分隔
        if not self.current_streaming_text:
            cursor.insertHtml("&nbsp;")

        self.current_streaming_text += char
        # 使用HTML插入黑色文本
        char_escaped = char.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        cursor.insertHtml(f'<span style="color: #000000;">{char_escaped}</span>')

        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_streaming_chunk(self, chunk: str):
        """流式传输 - 接收文本片段"""
        self._response_started = True
        self._kick_request_watchdog("streaming_chunk")
        # 停止加载动画
        if hasattr(self, '_loading_active') and self._loading_active:
            self._stop_loading_animation()

        # 检查是否是日语文本
        if chunk.startswith("[日语]"):
            japanese_text = chunk[4:].strip()  # 移除[日语]前缀
            print(f"[流式传输] 检测到日语文本: {japanese_text}")
            self._on_japanese_text_ready(japanese_text)
            return

        # 表情标签可以出现在任意位置；它们是控制信号，不是聊天文本
        for emotion in extract_emotions(chunk):
            print(f"[流式传输] 检测到表情标签: {emotion}")
            self._on_emotion_ready(emotion)

        chunk = clean_stream_display_text(chunk)
        if not chunk:
            return

        # 使用 QTextCursor 插入带颜色的文本片段
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        # 如果是第一个片段，先插入空格分隔
        if not self.current_streaming_text:
            cursor.insertHtml("&nbsp;")

        self.current_streaming_text += chunk
        # 使用HTML插入黑色文本
        chunk_escaped = chunk.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        cursor.insertHtml(f'<span style="color: #000000;">{chunk_escaped}</span>')

        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_preset_streaming_complete(self, full_text: str, emotion: str):
        """预设回答打字机效果完成"""
        # 设置表情
        if hasattr(self, 'character') and self.character:
            self.character.set_emotion(emotion)

        # 将预设回复添加到AI对话历史，保持上下文连贯
        if hasattr(self, 'ai_manager') and self.ai_manager:
            self.ai_manager.conversation_history.append({"role": "assistant", "content": full_text})

        self._restore_input_controls()

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
        self._kick_request_watchdog("audio_status")
        print(f"[音频状态] {status}")

    def _on_audio_ready(self, audio_source: str):
        """音频准备好，开始播放（支持URL和本地文件）"""
        self._kick_request_watchdog("audio_ready", 5000)
        print(f"[音频播放] _on_audio_ready 被调用，音频源: {audio_source}")
        if audio_source:
            if audio_source.startswith('http://') or audio_source.startswith('https://'):
                print(f"[音频播放] 检测到URL，直接播放")
            else:
                print(f"[音频播放] 检测到本地文件，检查文件是否存在: {Path(audio_source).exists()}")
            self.play_vocu_audio(audio_source)
        else:
            print(f"[音频播放] 音频源为空")

    def _stop_vocu_backends(self):
        """停止当前 Vocu 播放后端，避免多个播放器重叠。"""
        if hasattr(self, "network_stream_player") and self.network_stream_player:
            try:
                self.network_stream_player.stop()
                self.network_stream_player.wait(500)
            except Exception as exc:
                print(f"[网络流播放器] 停止失败: {exc}")
            self.network_stream_player = None

        if hasattr(self, "media_player"):
            try:
                self.media_player.stop()
            except Exception:
                pass

    def _on_network_stream_started(self, player):
        if getattr(self, "network_stream_player", None) is not player:
            return
        print("[网络流播放器] 已进入播放状态")
        if hasattr(self, 'character') and self.character and not self.character.is_speaking:
            print("[表情] 网络流开始播放，启动说话动画")
            self.character.start_speaking()

    def _on_network_stream_finished(self, player):
        if getattr(self, "network_stream_player", None) is not player:
            print("[网络流播放器] 忽略旧实例的结束信号")
            return
        print("[网络流播放器] 播放结束")
        if hasattr(self, 'character') and self.character and self.character.is_speaking:
            print("[表情] 网络流播放结束，停止说话动画")
            self.character.stop_speaking()
        self.network_stream_player = None

    def _on_network_stream_error(self, player, audio_source: str, error_msg: str):
        if getattr(self, "network_stream_player", None) is not player:
            print("[网络流播放器] 忽略旧实例的错误信号")
            return
        print(f"[网络流播放器] 播放失败，准备回退。error={error_msg}")
        self.network_stream_player = None

        cached_audio = None
        if (
            audio_source.startswith('http://') or audio_source.startswith('https://')
        ) and getattr(self, "audio_generator", None):
            cached_audio = self.audio_generator.cache_audio_to_local(audio_source)

        if cached_audio:
            print(f"[网络流播放器] 回退到本地缓存播放: {cached_audio}")
            self.play_vocu_audio(cached_audio)
            return

        if audio_source.startswith('http://') or audio_source.startswith('https://'):
            print("[网络流播放器] 本地缓存失败，回退到 Qt URL 播放")
            self._play_vocu_audio_with_qt(audio_source)

    def _play_vocu_audio_with_qt(self, audio_source: str):
        """作为兜底方案，使用 Qt 多媒体播放远程 URL。"""
        if not hasattr(self, 'media_player'):
            self.media_player = QMediaPlayer()
            self.audio_output = QAudioOutput()
            self.media_player.setAudioOutput(self.audio_output)
            self.audio_output.setVolume(1.0)
            if hasattr(self.media_player, 'setBufferDuration'):
                self.media_player.setBufferDuration(100)
                print("[音频播放] Qt 回退播放器已设置最小缓冲时长")
            self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)

        if hasattr(self, 'character') and self.character:
            print("[表情] 准备在 Qt 回退播放时启动说话动画")

        self.media_player.setSource(QUrl(audio_source))
        self.media_player.play()
        print(f"[音频播放] Qt 回退直接播放URL: {audio_source}")

    def _on_playback_state_changed(self, state):
        """播放状态变化时处理"""
        print(f"[播放状态] 状态变化: {state}, PlayingState: {QMediaPlayer.PlaybackState.PlayingState}")
        
        if state == QMediaPlayer.PlaybackState.PlayingState:
            # 音频开始播放，启动说话动画
            if hasattr(self, 'character') and self.character and not self.character.is_speaking:
                print(f"[表情] 音频开始播放，启动说话动画")
                self.character.start_speaking()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            # 音频停止播放，停止说话动画
            if hasattr(self, 'character') and self.character and self.character.is_speaking:
                print(f"[表情] 音频停止播放，停止说话动画")
                self.character.stop_speaking()

    def _on_japanese_text_ready(self, japanese_text: str):
        """日语文本准备好，显示在人物下方"""
        self._response_started = True
        self._kick_request_watchdog("japanese_text_ready")
        print(f"[调试] _on_japanese_text_ready 被调用, 日语文本: {japanese_text}")
        print(f"[调试] hasattr(self, 'character')={hasattr(self, 'character')}, hasattr(self, 'audio_mode')={hasattr(self, 'audio_mode')}")
        if hasattr(self, 'audio_mode'):
            print(f"[调试] self.audio_mode={self.audio_mode}")
        
        if hasattr(self, 'character') and self.character:
            self.character.set_japanese_text(japanese_text)
            
            # 只在非音频模式下启动说话动画
            # 音频模式下，张嘴动画在音频播放时启动
            audio_active = bool(getattr(self, "audio_available", False))
            print(f"[音频模式检查] hasattr(self, 'audio_mode')={hasattr(self, 'audio_mode')}, self.audio_mode={getattr(self, 'audio_mode', 'N/A')}, audio_available={audio_active}")
            
            if not audio_active:
                print(f"[表情] 非音频模式，启动说话动画")
                try:
                    self.character.start_speaking()
                    
                    # 固定播放3秒的说话动画
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
        print(f"[输入] AI流式传输完成，准备恢复输入。emotion={emotion}, audio_path={bool(audio_path)}")
        self._restore_input_controls()

        self.current_streaming_text = ""
        
        # 保存对话历史（如果启用了永久记忆）
        if self.permanent_memory and self.ai_manager:
            self.ai_manager.save_conversation()

    def _on_ai_error(self, error_msg: str):
        """AI调用出错时的回调"""
        print(f"[输入] AI调用出错，准备恢复输入。error={error_msg}")
        if error_msg == "timeout":
            # 显示超时消息
            timeout_message = "不好意思，我想我这边网络有点问题，我们稍后再聊这个话题吧"
            self.current_streaming_text += f"\n{timeout_message}"
        else:
            self.current_streaming_text += f"\n[错误: {error_msg}]"
        
        # 使用QTextCursor更新显示
        try:
            cursor = self.chat_history.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            error_escaped = self.current_streaming_text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            cursor.insertHtml(f'<span style="color: #FF0000;">{error_escaped}</span>')
            # 滚动到底部
            scrollbar = self.chat_history.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            print(f"更新错误显示失败: {e}")

        self._restore_input_controls()

    def _set_input_controls_enabled(self, enabled: bool, reason: str = ""):
        """统一管理输入控件状态，便于排查卡死/未恢复问题。"""
        self._chat_request_active = not enabled
        self._response_started = False if not enabled else self._response_started
        self.input_field.setEnabled(enabled)
        self.input_field.setReadOnly(not enabled)
        self.send_button.setEnabled(enabled)
        self.attach_button.setEnabled(enabled)
        state = "启用" if enabled else "禁用"
        print(f"[输入] {state}输入控件，reason={reason}, active={self._chat_request_active}")

        if enabled:
            self._request_watchdog.stop()
            self._response_started = False
            self.input_field.setFocus()
            self.input_field.activateWindow()
        else:
            self._kick_request_watchdog("request_started", 8000)

    def _restore_input_controls(self):
        """确保任何 worker 结束路径都会恢复输入控件。"""
        worker_type = type(self.current_worker).__name__ if self.current_worker is not None else "None"
        print(f"[输入] _restore_input_controls 被调用，worker={worker_type}")
        self._set_input_controls_enabled(True, f"restore_from_{worker_type}")
        self.current_worker = None
    
    def add_message(self, sender: str, text: str, color: str):
        """添加完整消息到历史 - 人名用指定颜色，文本用黑色"""
        self.chat_history.append(
            f'<span style="color: {color}; font-weight: bold;">{sender}:</span> '
            f'<span style="color: #000000;">{text}</span>'
        )
        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def add_message_with_image(self, sender: str, text: str, color: str, image_path: str):
        """添加带图片的消息到历史"""
        image_data_url = to_data_url(image_path, max_side=480, jpeg_quality=80)

        # 构建HTML（限制图片最大宽度）
        html = f'<span style="color: {color}; font-weight: bold;">{sender}:</span>'
        if text:
            html += f' <span style="color: #000000;">{text}</span>'
        html += f'<br><img src="{image_data_url}" style="max-width: 200px; max-height: 150px; border-radius: 5px; margin-top: 5px;">'

        self.chat_history.append(html)
        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def get_response_text(self, audio_name: str) -> str:
        """根据音频文件名获取对应的文本 - 扩展版本"""
        text_map = {
            # 问候语
            "hello": "你好。",
            "nice_to_meet_okabe": "很高兴见到你，冈部。",
            "pleased_to_meet_you": "很高兴认识你。",
            "look_forward_to_working": "期待与你合作。",
            
            # Christina相关
            "christina": "我说了不要叫我克里斯蒂娜！",
            "dont_call_me_like_that": "不要那样叫我！",
            "dont_add_tina": "不要加蒂娜！",
            "who_the_hell_christina": "谁是克里斯蒂娜啊！",
            "why_christina": "为什么是克里斯蒂娜？",
            "memories_christina": "克里斯蒂娜的记忆...",
            "should_christina": "应该叫克里斯蒂娜吗...",
            
            # 帮助/询问
            "could_i_help": "有什么我可以帮忙的吗？",
            "what_do_you_want": "你想要什么？",
            "ask_me_whatever": "尽管问吧。",
            "what_is_it": "什么事？",
            
            # 道歉/确认
            "sorry": "对不起。",
            "i_guess": "我想是吧。",
            "i_see": "我明白了。",
            "ok": "好的。",
            "nice": "不错。",
            "heheh": "呵呵。",
            "you_sure": "你确定吗？",
            "still_not_happy": "还是不太高兴。",
            
            # 疑问
            "huh_why_say": "嗯？为什么这么说？",
            "sounds_tough": "听起来很困难。",
            "humans_software": "人类就像软件一样。",
            
            # 记忆相关
            "memory_complex": "记忆是很复杂的。",
            "modifying_memories_impossible": "修改记忆是不可能的。",
            "secret_diary": "秘密日记...",
            
            # 变态相关
            "pervert_confirmed": "确认是变态。",
            "perverts_go_to_hell": "变态去死吧！",
            "pervert_idot_wanttodie": "你这个变态白痴，想死吗？",
            "devilish_pervert": "恶魔般的变态。",
            "this_guy_hopeless": "这家伙没救了。",
            
            # 前辈相关
            "senpai_question": "前辈？",
            "senpai_please_dont_tell": "前辈，请不要告诉别人...",
            "uh_senpai": "呃，前辈...",
            "senpai_who_is_this": "前辈，这是谁？",
            "senpai_what_we_talkin": "前辈，我们在说什么？",
            "senpai_questionmark": "前辈？？",
            "whats_so_funny_senpai": "前辈，有什么好笑的？",
            
            # 情绪表达
            "gah": "啊！",
            "gah_extended": "啊啊啊！",
            "daga_kotowaru": "但是我拒绝！",
            
            # 时间相关
            "tm_you_said": "你是说...",
            "tm_too_early": "太早了。",
            "tm_nonsense": "胡说八道。",
            "tm_not_possible": "不可能。",
            "tm_scientist_no_evidence": "科学家没有证据。",
            "tm_we_dont_know": "我们不知道。",

            # 其他
            "ask_me_whatever": "尽管问我任何事。",
            "happy": "开心~",
            "sad": "难过...",
            "angry": "生气！",
            "pissed": "愤怒！",
        }
        return text_map.get(audio_name, "...")
    
    def play_audio(self, audio_name: str, character=None):
        """播放音频 - 自动设置表情和动画"""
        audio_path = AUDIO_DIR / f"{audio_name}.ogg"
        if audio_path.exists():
            # 自动设置表情
            if character:
                japanese_text = VoiceDialog.get_japanese_text_for_audio(audio_name)
                if japanese_text:
                    character.set_japanese_text(japanese_text)

                emotion = VoiceDialog.get_emotion_for_audio(audio_name)
                character.set_emotion(emotion)
            
            self.player = AudioPlayer(audio_path)
            # 如果有角色组件，连接动画信号
            if character:
                self.player.started.connect(character.start_speaking)
                self.player.finished.connect(character.stop_speaking)
            self.player.start()
    
    def play_vocu_audio(self, audio_source: str):
        """播放Vocu生成的音频（支持URL和本地文件）"""
        try:
            self._stop_vocu_backends()

            if audio_source.startswith('http://') or audio_source.startswith('https://'):
                print(f"[音频播放] 优先使用专用网络流播放器: {audio_source}")
                self.network_stream_player = NetworkStreamPlayer(audio_source)
                self.network_stream_player.playback_started.connect(
                    lambda player=self.network_stream_player: self._on_network_stream_started(player)
                )
                self.network_stream_player.finished.connect(
                    lambda player=self.network_stream_player: self._on_network_stream_finished(player)
                )
                self.network_stream_player.error.connect(
                    lambda error_msg, source=audio_source, player=self.network_stream_player:
                    self._on_network_stream_error(player, source, error_msg)
                )
                self.network_stream_player.start()
            else:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(str(audio_source))
                pygame.mixer.music.play()
                
                print(f"[音频播放] 播放本地文件: {audio_source}")
                
                if hasattr(self, 'character') and self.character:
                    print(f"[表情] 开始说话动画")
                    self.character.start_speaking()
                def check_audio_done():
                    if not pygame.mixer.music.get_busy():
                        print(f"[表情] 停止说话动画")
                        if hasattr(self, 'character') and self.character:
                            self.character.stop_speaking()
                    else:
                        QTimer.singleShot(100, check_audio_done)
                QTimer.singleShot(100, check_audio_done)
        except Exception as e:
            print(f"播放Vocu音频失败: {e}")
            import traceback
            traceback.print_exc()
