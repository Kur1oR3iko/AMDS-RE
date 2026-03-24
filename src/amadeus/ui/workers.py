"""
工作线程模块 - 包含AI对话、打字机效果等后台任务
"""
import re
import time
import random
import base64
from pathlib import Path
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal


class ChatWorker(QThread):
    """AI对话工作线程 - 流式传输文本并解析表情标签，支持图片和音频生成"""
    emotion_ready = pyqtSignal(str)
    chunk_ready = pyqtSignal(str)
    response_complete = pyqtSignal(str, str, str)
    error_occurred = pyqtSignal(str)
    audio_status = pyqtSignal(str)
    audio_ready = pyqtSignal(str)
    japanese_text_ready = pyqtSignal(str)

    def __init__(self, ai_manager, user_input: str, image_path: str = None,
                 audio_generator=None, voice_id: str = None, enable_audio: bool = False, 
                 max_tokens: int = 200):
        super().__init__()
        self.ai_manager = ai_manager
        self.user_input = user_input
        self.image_path = image_path
        self.audio_generator = audio_generator
        self.voice_id = voice_id
        self.enable_audio = enable_audio
        self.max_tokens = max_tokens
        self._is_running = True
        self._start_time = None

    def run(self):
        try:
            self._start_time = time.time()
            
            use_audio_mode = self.enable_audio and self.audio_generator and self.voice_id
            
            if use_audio_mode:
                self.audio_status.emit("生成回复...")
                
                if self.image_path:
                    with open(self.image_path, 'rb') as f:
                        img_base64 = base64.b64encode(f.read()).decode()

                    ext = Path(self.image_path).suffix.lower()
                    mime_type = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.bmp': 'image/bmp',
                        '.gif': 'image/gif'
                    }.get(ext, 'image/png')

                    user_content = [
                        {"type": "text", "text": self.user_input if self.user_input else "请描述这张图片"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_base64}"}}
                    ]
                else:
                    user_content = self.user_input

                self.ai_manager.conversation_history.append({"role": "user", "content": user_content})

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

                messages = [
                    {"role": "system", "content": self.ai_manager.BILINGUAL_GENERATION_PROMPT}
                ] + (self.ai_manager.conversation_history if self.ai_manager.permanent_memory else self.ai_manager.conversation_history[-100:])

                response = self.ai_manager.client.chat.completions.create(
                    model=self.ai_manager.current_model,
                    messages=messages,
                    temperature=0.8,
                    max_tokens=self.max_tokens,
                    stream=True,
                    extra_body={"thinking": {"type": "disabled"}}
                )

                full_content = ""
                japanese_text = ""
                chinese_text = ""
                emotion = "normal"

                for chunk in response:
                    if not self._is_running:
                        break
                    if time.time() - self._start_time > 15:
                        self.error_occurred.emit("timeout")
                        return
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_content += chunk.choices[0].delta.content

                if not self._is_running:
                    return

                emotion = "normal"
                japanese_text = ""
                chinese_text = ""

                try:
                    print(f"[音频模式] 完整内容: {full_content}")

                    emotion_matches = re.findall(r'\[([^\]]+)\]', full_content)
                    if emotion_matches:
                        emotion = emotion_matches[-1]
                        full_content = re.sub(r'\[[^\]]+\]', '', full_content).strip()
                        print(f"[音频模式] 提取表情: {emotion}, 剩余内容: {full_content}")

                    if '|' in full_content:
                        lines = full_content.strip().split('\n')
                        japanese_parts = []
                        chinese_parts = []
                        for line in lines:
                            if '|' in line:
                                jp_part, cn_part = line.split('|', 1)
                                japanese_parts.append(jp_part.strip())
                                chinese_parts.append(cn_part.strip())
                            else:
                                has_japanese = bool(re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]', line))
                                if has_japanese:
                                    japanese_parts.append(line.strip())
                                else:
                                    chinese_parts.append(line.strip())
                        japanese_text = ''.join(japanese_parts)
                        chinese_text = ''.join(chinese_parts)
                        print(f"[音频模式] 分割结果 - 日语: {japanese_text}, 中文: {chinese_text}")
                    else:
                        has_japanese = bool(re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]', full_content))
                        if has_japanese:
                            japanese_text = full_content
                            chinese_text = self.ai_manager._translate_to_chinese(japanese_text)
                        else:
                            chinese_text = full_content
                            japanese_text = self.ai_manager._translate_to_japanese(chinese_text)
                except Exception as e:
                    print(f"解析响应失败: {e}")
                    import traceback
                    traceback.print_exc()

                self.emotion_ready.emit(emotion)

                audio_path = ""
                if japanese_text and self.audio_generator and self.voice_id:
                    self.japanese_text_ready.emit(japanese_text)
                    self.audio_status.emit("生成音频...")

                    def audio_callback(status: str):
                        self.audio_status.emit(status)

                    from ..utils import get_config_manager
                    config = get_config_manager()
                    async_audio = config.get("async_audio_generation", False)

                    if async_audio:
                        audio_url = self.audio_generator.generate_audio(
                            japanese_text,
                            self.voice_id,
                            language="ja",
                            callback=audio_callback
                        )
                    else:
                        audio_url = self.audio_generator.generate_audio_sync(
                            japanese_text,
                            self.voice_id,
                            language="ja",
                            callback=audio_callback
                        )

                    if audio_url:
                        self.audio_ready.emit(audio_url)
                        audio_path = audio_url

                if chinese_text:
                    for char in chinese_text:
                        if not self._is_running:
                            break
                        self.chunk_ready.emit(char)
                        self.msleep(30)

                self.ai_manager.conversation_history.append({"role": "assistant", "content": chinese_text})
                
                self.response_complete.emit(chinese_text, emotion, audio_path)

            else:
                emotion = "normal"
                emotion_emitted = False
                japanese_emitted = False

                for emotion, chunk_text in self.ai_manager.get_response_stream(self.user_input, self.image_path):
                    if not self._is_running:
                        break
                    if time.time() - self._start_time > 20:
                        self.error_occurred.emit("timeout")
                        return

                    if not emotion_emitted:
                        self.emotion_ready.emit(emotion)
                        emotion_emitted = True

                    if chunk_text.startswith("[日语]"):
                        japanese_text = chunk_text[4:].strip()
                        print(f"[普通模式] 发射日语文本: {japanese_text}")
                        self.japanese_text_ready.emit(japanese_text)
                        japanese_emitted = True
                    else:
                        self.chunk_ready.emit(chunk_text)

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
    char_ready = pyqtSignal(str)
    typing_complete = pyqtSignal(str, str)
    
    def __init__(self, text: str, emotion: str = "normal", char_delay: int = 50):
        super().__init__()
        self.text = text
        self.emotion = emotion
        self.char_delay = char_delay
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


class PresetSelectorWorker(QThread):
    """预设选择工作线程"""
    preset_selected = pyqtSignal(str)
    error_occurred = pyqtSignal()
    
    def __init__(self, ai_manager, user_text: str, presets: list):
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
