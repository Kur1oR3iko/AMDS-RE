"""Qt worker threads for chat and typewriter effects."""

import re
import threading
import time

from PyQt6.QtCore import QThread, pyqtSignal

from core.app_config import DEFAULT_VOCU_ASYNC_MODE, DEFAULT_VOCU_FLASH_MODE, DEFAULT_VOCU_REALTIME_MODE
from core.reply_parser import format_image_history_text, parse_bilingual_response
from services.ai_manager import AIChatManager
from utils.image_utils import encode_image_data_url
from utils.thread_pool import submit_io


def split_initial_tts_segment(text: str) -> tuple[str, str]:
    """取出第一个自然日语句子；较长句子也可在读点处分段。"""
    cleaned = (text or "").lstrip()
    while cleaned.startswith("["):
        closing = cleaned.find("]")
        if closing < 0:
            return "", ""
        cleaned = cleaned[closing + 1:].lstrip()

    sentence = re.search(r"[。！？!?]+[」』】）)]*", cleaned)
    comma = re.search(r"[、，,]", cleaned)
    boundary = sentence.end() if sentence else None
    if comma and comma.end() >= 10 and (boundary is None or comma.end() < boundary):
        boundary = comma.end()
    if boundary is None:
        return "", cleaned
    return cleaned[:boundary].strip(), cleaned[boundary:].strip()


def split_next_tts_segment(
    text: str,
    final: bool = False,
    max_chars: int = 32,
) -> tuple[str, str]:
    """按自然句界取下一段；极长无标点文本限制为适合低延迟 TTS 的长度。"""
    head, remainder = split_initial_tts_segment(text)
    if head and len(head) <= max_chars:
        return head, remainder

    cleaned = (text or "").strip()
    if head:
        cleaned = head
    elif len(cleaned) < max_chars and not final:
        return "", cleaned
    elif len(cleaned) <= max_chars:
        return cleaned, ""

    boundary = max_chars
    for marker in ("、", "，", ","):
        candidate = cleaned.rfind(marker, max_chars // 2, max_chars)
        if candidate >= max_chars // 2:
            boundary = max(boundary if boundary < max_chars else 0, candidate + 1)
    segment = cleaned[:boundary].strip()
    tail = cleaned[boundary:].strip()
    if head:
        tail = f"{tail}{remainder}".strip()
    return segment, tail

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
                 vocu_flash_mode: bool = DEFAULT_VOCU_FLASH_MODE,
                 vocu_realtime_mode: bool = DEFAULT_VOCU_REALTIME_MODE):
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
        self.vocu_realtime_mode = vocu_realtime_mode
        self._is_running = True
        self._start_time = None
        self._audio_futures = []

    def run(self):
        try:
            self._start_time = time.perf_counter()
            
            # 判断是否使用音频模式（即使有图片也使用音频模式）
            # 只有三项都就绪时才走音频分支：开关、生成器和声音 ID
            use_audio_mode = self.enable_audio and self.audio_generator and self.voice_id
            
            if use_audio_mode:
                # 音频模式仍保持模型流式输出，文本和 TTS 各自尽早推进。
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
                self.ai_manager.append_message("user", history_user_content)

                # 流式生成双语回复
                messages = self.ai_manager.context_messages()
                if self.image_path:
                    for index in range(len(messages) - 1, -1, -1):
                        if messages[index].get("role") == "user":
                            messages[index] = {"role": "user", "content": user_content}
                            break

                audio_segment_count = 0
                audio_results: dict[int, str | None] = {}
                audio_results_lock = threading.Lock()
                next_audio_to_emit = 1
                audio_protocol_closed = False
                audio_emotion_emitted = False
                japanese_emitted = False
                first_delta_logged = False
                streamed_chinese_text = ""
                observed_japanese_text = ""
                pending_japanese_text = ""
                audio_generation_slots = threading.BoundedSemaphore(2)

                def generate_audio_segment(segment_index: int, japanese_text: str):
                    nonlocal next_audio_to_emit
                    segment_started = time.perf_counter()
                    audio_url = None
                    try:
                        with audio_generation_slots:
                            if not self._is_running:
                                return
                            print(f"[音频生成] 开始生成第 {segment_index} 段")
                            audio_url = self.audio_generator.generate_audio(
                                text=japanese_text,
                                voice_id=self.voice_id,
                                language="ja",
                                async_mode=self.vocu_async_mode,
                                flash_mode=self.vocu_flash_mode,
                                realtime_mode=self.vocu_realtime_mode,
                            )
                        if audio_url:
                            print(
                                f"[音频生成] 第 {segment_index} 段播放地址已就绪，"
                                f"耗时 {time.perf_counter() - segment_started:.2f} 秒"
                            )
                        else:
                            self.audio_status.emit(f"第 {segment_index} 段音频生成失败")
                    except Exception as exc:
                        print(f"[音频生成] 第 {segment_index} 段异常: {exc}")
                        self.audio_status.emit(f"第 {segment_index} 段音频生成失败")

                    ready_urls = []
                    with audio_results_lock:
                        audio_results[segment_index] = audio_url
                        while next_audio_to_emit in audio_results:
                            ready = audio_results.pop(next_audio_to_emit)
                            next_audio_to_emit += 1
                            if ready:
                                ready_urls.append(ready)
                    if self._is_running:
                        for ready in ready_urls:
                            self.audio_ready.emit(ready)

                def queue_audio_segment(japanese_text: str):
                    nonlocal audio_segment_count
                    normalized = (japanese_text or "").strip()
                    if not normalized or not self._is_running:
                        return
                    audio_segment_count += 1
                    print(
                        f"[音频生成] 第 {audio_segment_count} 段已入队，"
                        f"距请求开始 {time.perf_counter() - self._start_time:.2f} 秒"
                    )
                    future = submit_io(generate_audio_segment, audio_segment_count, normalized)
                    self._audio_futures.append(future)

                def queue_streamed_audio_segments(japanese_prefix: str, final: bool = False):
                    nonlocal audio_protocol_closed, observed_japanese_text, pending_japanese_text
                    if audio_protocol_closed:
                        return
                    cleaned = re.sub(r"\[[^\]]+\]", "", japanese_prefix or "").strip()
                    if cleaned.startswith(observed_japanese_text):
                        pending_japanese_text += cleaned[len(observed_japanese_text):]
                        observed_japanese_text = cleaned
                    elif not observed_japanese_text:
                        pending_japanese_text = cleaned
                        observed_japanese_text = cleaned
                    else:
                        # Responses 流通常只追加；前缀异常改写时等最终解析结果兜底。
                        if final:
                            pending_japanese_text = cleaned
                            observed_japanese_text = cleaned
                        else:
                            return

                    while pending_japanese_text:
                        segment, remainder = split_next_tts_segment(
                            pending_japanese_text,
                            final=final,
                        )
                        if not segment:
                            break
                        queue_audio_segment(segment)
                        pending_japanese_text = remainder
                    if final:
                        audio_protocol_closed = True

                def emit_chinese_progress(chinese_text: str):
                    nonlocal streamed_chinese_text
                    candidate = (chinese_text or "").strip()
                    if not candidate:
                        return
                    if candidate.startswith(streamed_chinese_text):
                        delta = candidate[len(streamed_chinese_text):]
                    elif not streamed_chinese_text:
                        delta = candidate
                    else:
                        # 模型输出是追加式的；若提供商改写了已输出前缀，避免重复显示。
                        return
                    if delta:
                        self.chunk_ready.emit(delta)
                        streamed_chinese_text = candidate

                # 流式收集完整内容
                full_content = ""
                audio_generation_prompt = self.ai_manager.BILINGUAL_GENERATION_PROMPT + """

语音低延迟附加要求：日语部分优先用一个自然、承载实际语义的短句开场，
建议约 6～14 个日文字符并以「。」「！」「？」结束，然后再继续完整回答。
不要为了短句添加与用户问题无关的寒暄；仍然只能使用一个半角竖线分隔完整日语和中文。"""
                for content in self.ai_manager.stream_text(
                    audio_generation_prompt,
                    messages,
                    self.max_tokens,
                    0.8,
                ):
                    if not self._is_running:
                        break
                    # 检查超时
                    if time.perf_counter() - self._start_time > 90:
                        self.error_occurred.emit("timeout")
                        return
                    if not first_delta_logged:
                        first_delta_logged = True
                        print(
                            "[音频延迟] 模型首个文本块到达，"
                            f"耗时 {time.perf_counter() - self._start_time:.2f} 秒"
                        )
                    full_content += content

                    # 每个完整自然句一出现就合成；长回复可继续形成第 3、4 段。
                    # 合成端最多同时提交两条，播放端严格顺序并只预连接下一条。
                    if not audio_protocol_closed:
                        japanese_prefix, separator, _ = full_content.partition("|")
                        queue_streamed_audio_segments(japanese_prefix, final=bool(separator))
                        if audio_segment_count and not audio_emotion_emitted:
                            partial = parse_bilingual_response(japanese_prefix, None, None)
                            self.emotion_ready.emit(partial.emotion)
                            audio_emotion_emitted = True
                        if separator:
                            partial = parse_bilingual_response(full_content, None, None)
                            if partial.japanese_text and not japanese_emitted:
                                self.japanese_text_ready.emit(partial.japanese_text)
                                japanese_emitted = True
                            emit_chinese_progress(partial.chinese_text)

                    if not japanese_emitted and "|" in full_content:
                        partial = parse_bilingual_response(full_content, None, None)
                        if partial.japanese_text:
                            self.japanese_text_ready.emit(partial.japanese_text)
                            japanese_emitted = True

                if not self._is_running:
                    return

                try:
                    # 统一解析 AI 的多段输出，避免表情、日文、中文分散在不同分支里
                    print(f"[音频模式] 双语回复接收完成，共 {len(full_content)} 个字符")
                    parsed = parse_bilingual_response(
                        full_content,
                        self.ai_manager._translate_to_japanese,
                        self.ai_manager._translate_to_chinese,
                    )
                    emotion = parsed.emotion
                    japanese_text = parsed.japanese_text
                    chinese_text = parsed.chinese_text
                    print(
                        f"[音频模式] 解析完成 - 表情: {emotion}, "
                        f"日语 {len(japanese_text)} 字符, 中文 {len(chinese_text)} 字符"
                    )
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

                if not japanese_emitted:
                    self.japanese_text_ready.emit(japanese_text)
                if not audio_protocol_closed:
                    queue_streamed_audio_segments(japanese_text, final=True)

                audio_path = None

                # 补发模型结束事件中尚未流出的尾部，绝不重复已显示文本。
                if self._is_running:
                    emit_chinese_progress(chinese_text)

                # 添加到历史
                self.ai_manager.append_message("assistant", chinese_text)
                self.ai_manager.schedule_memory_compaction()
                self.ai_manager.schedule_fact_extraction(self.user_input)
                
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
                    if time.perf_counter() - self._start_time > 20:
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
        for future in self._audio_futures:
            future.cancel()

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
