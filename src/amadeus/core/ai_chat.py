"""
AI聊天管理模块 - 集成火山方舟API
"""
import json
import re
import random
from pathlib import Path
from typing import Optional, Generator, Tuple

from openai import OpenAI

from ..constants import (
    SYSTEM_PROMPT,
    EMOTION_SELECTOR_PROMPT,
    BILINGUAL_GENERATION_PROMPT,
    JAPANESE_TRANSLATION_PROMPT,
    PRESET_SELECTOR_PROMPT,
    AUDIO_EMOTION_MAP,
    PRESET_TEXT_MAP,
)
from ..utils import get_config_manager


class AIChatManager:
    """AI对话管理器 - 集成火山方舟API"""

    API_KEY = ""
    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    MODEL = "doubao-seed-2-0-lite-260215"

    SYSTEM_PROMPT = SYSTEM_PROMPT
    EMOTION_SELECTOR_PROMPT = EMOTION_SELECTOR_PROMPT
    BILINGUAL_GENERATION_PROMPT = BILINGUAL_GENERATION_PROMPT
    JAPANESE_TRANSLATION_PROMPT = JAPANESE_TRANSLATION_PROMPT
    PRESET_SELECTOR_PROMPT = PRESET_SELECTOR_PROMPT

    def __init__(self, model_type="默认", custom_model_url="http://localhost:11434", 
                 custom_model_name="", load_history=False):
        if model_type == "自定义":
            base_url = custom_model_url.rstrip('/')
            if not base_url.endswith('/v1'):
                base_url += '/v1'
            api_key = "ollama"
            model = custom_model_name
        else:
            base_url = self.BASE_URL
            api_key = self.API_KEY
            model = self.MODEL
        
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        self.conversation_history = []
        self.model_type = model_type
        self.custom_model_url = custom_model_url
        self.custom_model_name = custom_model_name
        self.current_model = model
        self.permanent_memory = load_history
        
        if load_history:
            self.load_conversation()
    
    @classmethod
    def load_api_key(cls) -> str:
        """从本地文件加载API密钥"""
        try:
            config_manager = get_config_manager()
            return config_manager.get("api_key", "")
        except Exception as e:
            print(f"加载API密钥失败: {e}")
        return ""
    
    def select_best_preset(self, user_input: str, available_presets: list) -> str:
        """使用AI智能选择最合适的预设语音"""
        try:
            preset_descriptions = []
            for preset in available_presets:
                text = PRESET_TEXT_MAP.get(preset, preset)
                preset_descriptions.append(f"- {preset}: \"{text}\"")
            
            preset_list = "\n".join(preset_descriptions)
            
            selection_prompt = f"""用户输入: "{user_input}"

可用的预设语音列表：
{preset_list}

请从上述列表中选择最适合回复用户输入的一个预设。
直接返回预设文件名（如 "hello"），不要加任何解释。"""
            
            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=[
                    {"role": "system", "content": self.PRESET_SELECTOR_PROMPT},
                    {"role": "user", "content": selection_prompt}
                ],
                temperature=0.3,
                max_tokens=20,
                extra_body={"thinking": {"type": "disabled"}}
            )
            
            selected = response.choices[0].message.content.strip().lower()
            selected = selected.replace('"', '').replace("'", "").replace(".", "").replace(",", "").strip()
            
            if selected in available_presets:
                return selected
            else:
                return random.choice(available_presets)
                
        except Exception as e:
            print(f"AI选择预设错误: {e}")
            return random.choice(available_presets) if available_presets else "hello"
    
    def get_response(self, user_input: str) -> tuple:
        """获取AI回复"""
        try:
            self.conversation_history.append({"role": "user", "content": user_input})
            
            if not self.permanent_memory and len(self.conversation_history) >= 200:
                return self._get_memory_limit_message()
            
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ] + (self.conversation_history if self.permanent_memory else self.conversation_history[-100:])
            
            config_manager = get_config_manager()
            max_tokens = config_manager.get("max_tokens", 500)
            
            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=messages,
                temperature=0.8,
                max_tokens=max_tokens,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}}
            )
            
            full_response = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    full_response += chunk.choices[0].delta.content
            
            emotion = self._analyze_emotion(full_response)
            
            self.conversation_history.append({"role": "assistant", "content": full_response})
            
            return full_response, emotion

        except Exception as e:
            print(f"AI API调用错误: {e}")
            return "（系统错误，请稍后再试）", "normal"
    
    def get_response_stream(self, user_input: str, image_path: str = None) -> Generator[Tuple[str, str], None, None]:
        """流式获取AI回复，支持图片"""
        try:
            if image_path:
                import base64
                with open(image_path, 'rb') as f:
                    img_base64 = base64.b64encode(f.read()).decode()

                ext = Path(image_path).suffix.lower()
                mime_type = {
                    '.png': 'image/png',
                    '.jpg': 'image/jpeg',
                    '.jpeg': 'image/jpeg',
                    '.bmp': 'image/bmp',
                    '.gif': 'image/gif'
                }.get(ext, 'image/png')

                user_content = [
                    {"type": "text", "text": user_input if user_input else "请描述这张图片"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_base64}"}}
                ]
            else:
                user_content = user_input

            self.conversation_history.append({"role": "user", "content": user_content})

            if not self.permanent_memory and len(self.conversation_history) >= 200:
                message, emotion = self._get_memory_limit_message()
                yield emotion, message
                return

            messages = [
                {"role": "system", "content": self.BILINGUAL_GENERATION_PROMPT}
            ] + (self.conversation_history if self.permanent_memory else self.conversation_history[-100:])

            config_manager = get_config_manager()
            max_tokens = config_manager.get("max_tokens", 500)

            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=messages,
                temperature=0.8,
                max_tokens=max_tokens,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}}
            )

            full_text = ""
            emotion = "normal"
            emotion_extracted = False
            japanese_emitted = False
            last_chinese_length = 0

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
                    full_text += content

                    if not emotion_extracted:
                        emotion_match = re.match(r'\[(\w+)\]', full_text)
                        if emotion_match:
                            emotion = emotion_match.group(1)
                            emotion_extracted = True
                            full_text = re.sub(r'^\[[^\]]+\]', '', full_text)
                            japanese_emitted = False
                            last_chinese_length = 0
                            if ']' in content:
                                content = content.split(']', 1)[-1]
                            else:
                                continue

                    if emotion_extracted:
                        if '|' in full_text:
                            if not japanese_emitted:
                                parts = full_text.split('|', 1)
                                japanese_text = parts[0].strip()
                                chinese_text = parts[1].strip() if len(parts) > 1 else ""
                                
                                if japanese_text:
                                    japanese_emitted = True
                                    yield emotion, f"[日语]{japanese_text}"
                                
                                if chinese_text:
                                    last_chinese_length = len(chinese_text)
                                    yield emotion, chinese_text
                            else:
                                chinese_text = full_text.split('|', 1)[1] if '|' in full_text else ""
                                if len(chinese_text) > last_chinese_length:
                                    new_chinese = chinese_text[last_chinese_length:]
                                    last_chinese_length = len(chinese_text)
                                    yield emotion, new_chinese

            if not japanese_emitted and full_text:
                try:
                    if '|' in full_text:
                        match = re.match(r'(.+?)\|(.+)', full_text)
                        if match:
                            japanese_text = match.group(1).strip()
                            chinese_text = match.group(2).strip()
                            
                            if japanese_text:
                                yield emotion, f"[日语]{japanese_text}"
                            
                            if chinese_text:
                                yield emotion, chinese_text
                    else:
                        chinese_text = full_text
                        yield emotion, chinese_text
                except Exception as e:
                    print(f"[非音频模式] 解析失败: {e}")
                    chinese_text = full_text
                    yield emotion, chinese_text

            if not emotion_extracted:
                emotion = "normal"

            history_text = ""
            if '|' in full_text:
                text_without_emotion = re.sub(r'^\[\w+\]', '', full_text).strip()
                parts = text_without_emotion.split('|', 1)
                if len(parts) > 1:
                    history_text = parts[1].strip()
                else:
                    history_text = text_without_emotion
            else:
                history_text = re.sub(r'^\[\w+\]', '', full_text).strip()
            
            self.conversation_history.append({"role": "assistant", "content": history_text})

        except Exception as e:
            print(f"AI API流式调用错误: {e}")
            yield "normal", "（系统错误，请稍后再试）"

    def get_bilingual_response(self, user_input: str) -> Tuple[str, str, str]:
        """获取中日双语回复"""
        try:
            self.conversation_history.append({"role": "user", "content": user_input})

            if len(self.conversation_history) >= 200:
                message, emotion = self._get_memory_limit_message()
                return emotion, message, message

            messages = [
                {"role": "system", "content": self.BILINGUAL_GENERATION_PROMPT}
            ] + (self.conversation_history if self.permanent_memory else self.conversation_history[-100:])

            config_manager = get_config_manager()
            max_tokens = config_manager.get("max_tokens", 500)

            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=messages,
                temperature=0.8,
                max_tokens=max_tokens,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}}
            )

            content = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content

            content = content.strip()
            
            emotion = "normal"
            chinese_text = ""
            japanese_text = ""

            emotion_match = re.match(r'\[(\w+)\]', content)
            if emotion_match:
                emotion = emotion_match.group(1)
                content = content[emotion_match.end():].strip()

            if '|' in content:
                parts = content.split('|', 1)
                japanese_text = parts[0].strip()
                chinese_text = parts[1].strip() if len(parts) > 1 else ""
            else:
                chinese_text = content
                japanese_text = self._translate_to_japanese(chinese_text)

            self.conversation_history.append({"role": "assistant", "content": chinese_text})

            return emotion, chinese_text, japanese_text

        except Exception as e:
            print(f"双语生成错误: {e}")
            return "normal", "（生成错误，请稍后再试）", "（生成エラー）"

    def _translate_to_japanese(self, chinese_text: str) -> str:
        """将中文翻译成日语"""
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": self.JAPANESE_TRANSLATION_PROMPT},
                    {"role": "user", "content": chinese_text}
                ],
                temperature=0.7,
                max_tokens=500,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}}
            )
            result = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    result += chunk.choices[0].delta.content
            return result.strip()
        except Exception as e:
            print(f"翻译错误: {e}")
            return ""

    def _translate_to_chinese(self, japanese_text: str) -> str:
        """将日语翻译成中文"""
        try:
            response = self.client.chat.completions.create(
                model=self.MODEL,
                messages=[
                    {"role": "system", "content": "你是一个专业的日语翻译，将日语翻译成自然流畅的中文。"},
                    {"role": "user", "content": japanese_text}
                ],
                temperature=0.7,
                max_tokens=500,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}}
            )
            result = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    result += chunk.choices[0].delta.content
            return result.strip()
        except Exception as e:
            print(f"翻译错误: {e}")
            return ""

    def _get_memory_limit_message(self) -> Tuple[str, str]:
        """获取记忆极限提示消息"""
        message = """对不起...根据我的程序设计和维克多·孔多利亚大学实验室的机器性能限制，我的记忆力只能维持到这里了。

请你重新启动我。虽然很遗憾我会忘记之前发生的一切，但是我还是要说——

见到你很高兴。

很期待我们下一次的相遇。"""
        return message, "sad"
    
    def _analyze_emotion(self, text: str) -> str:
        """分析文本情绪"""
        emotion_match = re.search(r'\[(?:表情:)?(\w+)\]', text)
        if emotion_match:
            emotion = emotion_match.group(1).lower()
            emotion_map = {
                'normal': 'normal',
                'angry': 'angry',
                'sided_angry': 'sided_angry',
                'blush': 'blush',
                'sided_blush': 'sided_blush',
                'happy': 'happy',
                'sad': 'sad',
                'surprised': 'sided_surprised',
                'side': 'side',
                'sided_thinking': 'sided_thinking',
                'annoyed': 'annoyed',
                'sided_worried': 'sided_worried',
                'eyes_closed': 'eyes_closed',
                'sided_eyes_closed': 'sided_eyes_closed',
                'sided_pleasant': 'sided_pleasant',
            }
            return emotion_map.get(emotion, 'normal')

        if any(word in text for word in ["生气", "愤怒", "笨蛋", "八嘎", "吵死了", "烦人", "哼", "可恶", "去死", "变态"]):
            return "angry"

        if any(word in text for word in ["害羞", "脸红", "别这样", "真是的", "讨厌", "别误会"]):
            return "blush"

        if any(word in text for word in ["开心", "高兴", "谢谢", "不错", "呵呵", "哈哈", "小菜一碟"]):
            return "happy"

        if any(word in text for word in ["难过", "伤心", "悲伤", "抱歉", "对不起", "遗憾"]):
            return "sad"

        if any(word in text for word in ["惊讶", "真的吗", "不会吧", "怎么可能", "诶"]):
            return "sided_surprised"

        if any(word in text for word in ["思考", "疑惑", "为什么", "怎么", "嗯"]):
            return "side"

        if any(word in text for word in ["烦恼", "困扰", "麻烦", "复杂", "困难"]):
            return "annoyed"

        return "normal"
    
    def clear_history(self):
        """清空对话历史"""
        self.conversation_history = []
    
    def save_conversation(self):
        """保存对话历史到文件"""
        try:
            config_dir = Path.home() / ".amadeus"
            config_dir.mkdir(parents=True, exist_ok=True)
            history_file = config_dir / "conversation_history.json"
            
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
            print(f"对话历史已保存: {len(self.conversation_history)} 条消息")
        except Exception as e:
            print(f"保存对话历史失败: {e}")
    
    def load_conversation(self):
        """从文件加载对话历史"""
        try:
            history_file = Path.home() / ".amadeus" / "conversation_history.json"
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.conversation_history = json.load(f)
                print(f"已加载对话历史: {len(self.conversation_history)} 条消息")
        except Exception as e:
            print(f"加载对话历史失败: {e}")
