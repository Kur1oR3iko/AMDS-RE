"""Qt worker threads for chat and typewriter effects."""

from PyQt6.QtCore import QThread, pyqtSignal

from core.app_config import DEFAULT_VOCU_ASYNC_MODE, DEFAULT_VOCU_FLASH_MODE
from core.reply_parser import format_image_history_text, parse_bilingual_response
from services.ai_manager import AIChatManager
from utils.image_utils import encode_image_data_url
from utils.thread_pool import submit_io

class ChatWorker(QThread):
    """AI对话工作线程 - 流式传输文本并解析表情标签，支持图片和音频生成"""
    emotion_ready = pyqtSignal(str)  # 表情已确定
    chunk_ready = pyqtSignal(str)  # 文本片段
    response_complete = pyqtSignal(str, str, str)  # 完整文本, 表情, 音频路径
    error_occurred = pyqtSignal(str)
    audio_status = pyqtSignal(str)  # 音频生成状态
    audio_ready = pyqtSignal(str)  # 音频已准备好，开始播放
    japanese_text_ready = pyqtSignal(str)  # 日语文本已准备好

    def __init__(self, ai_manager: AIChatManager, user_input: str, image_path: str = None,
                 audio_generator=None, voice_id: str = None, enable_audio: bool = False,
                 max_tokens: int = 200, vocu_async_mode: bool = DEFAULT_VOCU_ASYNC_MODE,
                 vocu_flash_mode: bool = DEFAULT_VOCU_FLASH_MODE):
        super().__init__()
        self.ai_manager = ai_manager
        self.user_input = user_input
        self.image_path = image_path
        self.audio_generator = audio_generator
        self.voice_id = voice_id
        self.enable_audio = enable_audio
        self.max_tokens = max_tokens
        self.vocu_async_mode = vocu_async_mode
        self.vocu_flash_mode = vocu_flash_mode
        self._is_running = True
        self._start_time = None

    def run(self):
        try:
            import time
            self._start_time = time.time()
            
            # 判断是否使用音频模式（即使有图片也使用音频模式）
            # 只有三项都就绪时才走音频分支：开关、生成器和声音 ID
            use_audio_mode = self.enable_audio and self.audio_generator and self.voice_id
            
            if use_audio_mode:
                # 优化流程：先生成文本和音频，准备好后同步显示
                self.audio_status.emit("生成回复...")
                
                # 处理用户输入（支持图片）
                if self.image_path:
                    # 图片只在这条请求里以 base64 发送，历史记录里会被压缩成文本占位
                    img_base64, mime_type = submit_io(
                        encode_image_data_url,
                        self.image_path,
                        1280,
                        85,
                    ).result()

                    # 构建包含图片的消息
                    user_content = [
                        {"type": "text", "text": self.user_input if self.user_input else "请描述这张图片"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_base64}"}}
                    ]
                else:
                    user_content = self.user_input

                # 添加用户输入到历史
                history_user_content = format_image_history_text(self.user_input, self.image_path) if self.image_path else self.user_input
                self.ai_manager.conversation_history.append({"role": "user", "content": history_user_content})

                # 检查记忆极限
                # 永久记忆功能开启时不显示记忆极限提示
                if not self.ai_manager.permanent_memory and len(self.ai_manager.conversation_history) >= 200:
                    message, emotion = self.ai_manager._get_memory_limit_message()
                    self.emotion_ready.emit(emotion)
                    for char in message:
                        if not self._is_running:
                            break
                        self.chunk_ready.emit(char)
                        self.msleep(30)
                    self.response_complete.emit(message, emotion, "")
                    return

                # 流式生成双语回复
                history_messages = self.ai_manager.conversation_history if self.ai_manager.permanent_memory else self.ai_manager.conversation_history[-100:]
                messages = [
                    {"role": "system", "content": self.ai_manager.BILINGUAL_GENERATION_PROMPT}
                ] + history_messages  # 永久记忆时使用全部历史，否则保留最近100轮对话
                if self.image_path and messages:
                    messages[-1] = {"role": "user", "content": user_content}

                response = self.ai_manager.client.chat.completions.create(
                    model=self.ai_manager.current_model,
                    messages=messages,
                    temperature=0.8,
                    max_tokens=self.max_tokens,
                    stream=True,
                    extra_body={"thinking": {"type": "disabled"}}
                )

                # 流式收集完整内容
                full_content = ""
                for chunk in response:
                    if not self._is_running:
                        break
                    # 检查超时
                    if time.time() - self._start_time > 20:
                        self.error_occurred.emit("timeout")
                        return
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_content += chunk.choices[0].delta.content

                if not self._is_running:
                    return

                try:
                    # 统一解析 AI 的多段输出，避免表情、日文、中文分散在不同分支里
                    print(f"[音频模式] 完整内容: {full_content}")
                    parsed = parse_bilingual_response(
                        full_content,
                        self.ai_manager._translate_to_japanese,
                        self.ai_manager._translate_to_chinese,
                    )
                    emotion = parsed.emotion
                    japanese_text = parsed.japanese_text
                    chinese_text = parsed.chinese_text
                    print(f"[音频模式] 解析结果 - 表情: {emotion}, 日语: {japanese_text}, 中文: {chinese_text}")
                except Exception as e:
                    print(f"解析响应失败: {e}")
                    import traceback
                    traceback.print_exc()
                    # 如果解析失败，使用原始内容
                    emotion = "normal"
                    chinese_text = full_content
                    japanese_text = ""

                # 发射表情
                self.emotion_ready.emit(emotion)

                # 先显示日语文本
                self.japanese_text_ready.emit(japanese_text)

                # 在后台线程中生成音频，不阻塞中文文本显示
                audio_path = None
                if japanese_text and self._is_running:
                    # 检查超时
                    if time.time() - self._start_time > 20:
                        self.error_occurred.emit("timeout")
                        return
                    
                    def generate_audio_async():
                        try:
                            print(f"[音频生成] 开始生成音频")
                            audio_url = self.audio_generator.generate_audio(
                                text=japanese_text,
                                voice_id=self.voice_id,
                                language="ja",
                                async_mode=self.vocu_async_mode,
                                flash_mode=self.vocu_flash_mode
                            )
                            
                            if audio_url:
                                print(f"[音频生成] 获得音频URL: {audio_url}")
                                # 保留远程流地址，优先交给专门的网络流播放器处理
                                self.audio_ready.emit(audio_url)
                            else:
                                print(f"[音频生成] 音频URL为空")
                                self.audio_status.emit("音频生成失败")
                        except Exception as e:
                            print(f"[音频生成] 异常: {e}")
                            import traceback
                            traceback.print_exc()
                            self.audio_status.emit("音频生成失败")
                    
                    submit_io(generate_audio_async)

                # 立即流式显示中文文本（不等待音频生成）
                if self._is_running:
                    for char in chinese_text:
                        if not self._is_running:
                            break
                        self.chunk_ready.emit(char)
                        self.msleep(25)

                # 添加到历史
                self.ai_manager.conversation_history.append({"role": "assistant", "content": chinese_text})
                
                self.response_complete.emit(chinese_text, emotion, audio_path or "")

            else:
                # 普通模式：流式生成文本（支持图片）
                emotion = "normal"
                emotion_emitted = False
                japanese_emitted = False

                for emotion, chunk_text in self.ai_manager.get_response_stream(self.user_input, self.image_path):
                    if not self._is_running:
                        break
                    # 检查超时
                    if time.time() - self._start_time > 20:
                        self.error_occurred.emit("timeout")
                        return

                    if not emotion_emitted:
                        self.emotion_ready.emit(emotion)
                        emotion_emitted = True

                    # 检查是否是日语文本
                    if chunk_text.startswith("[日语]"):
                        japanese_text = chunk_text[4:].strip()  # 移除[日语]前缀
                        print(f"[普通模式] 发射日语文本: {japanese_text}")
                        self.japanese_text_ready.emit(japanese_text)
                        japanese_emitted = True
                    else:
                        # 流式显示中文文本
                        self.chunk_ready.emit(chunk_text)

                # 发射响应完成信号
                self.response_complete.emit("", emotion, "")

        except Exception as e:
            if str(e) == "timeout":
                self.error_occurred.emit("timeout")
            else:
                self.error_occurred.emit(str(e))

    def stop(self):
        self._is_running = False

class TypewriterWorker(QThread):
    """打字机效果工作线程 - 用于预设回答"""
    char_ready = pyqtSignal(str)  # 单个字符
    typing_complete = pyqtSignal(str, str)  # 完整文本, 表情
    
    def __init__(self, text: str, emotion: str = "normal", char_delay: int = 50):
        super().__init__()
        self.text = text
        self.emotion = emotion
        self.char_delay = char_delay  # 每个字符延迟毫秒
        self._is_running = True
    
    def run(self):
        for char in self.text:
            if not self._is_running:
                break
            self.char_ready.emit(char)
            self.msleep(self.char_delay)
        
        self.typing_complete.emit(self.text, self.emotion)
    
    def stop(self):
        self._is_running = False
