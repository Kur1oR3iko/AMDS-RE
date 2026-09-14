"""
AI 对话管理器
封装火山方舟（豆包）/ Ollama / Deepseek 的 API 调用，负责对话上下文管理、
流式生成、中日双语解析、预设语音选择等功能
"""

import json
import random
import re
import threading

from openai import OpenAI

from core.app_config import (
    DEEPSEEK_BASE_URL,
    DEEPSEEK_MODEL_OPTIONS,
    DEFAULT_DEEPSEEK_MODEL,
    DEFAULT_MODEL,
    DEFAULT_RESPONSES_BASE_URL,
    DEFAULT_RESPONSES_MODEL,
    LEGACY_MODEL_MAP,
    RESPONSES_PROVIDER_TYPE,
)
from core.character_skill import build_prompt_bundle
from core.reply_parser import (
    format_image_history_text,
    normalize_emotion,
    parse_bilingual_response,
)
from core.resources import get_config_dir, get_qsettings
from services.conversation_memory import ConversationMemory
from services.voice_dialog import VoiceDialog
from utils.image_utils import encode_image_data_url
from utils.thread_pool import submit_io


class AIChatManager:
    """
    AI 对话管理器
    通过 OpenAI 兼容协议对接火山方舟、Ollama 或 Deepseek，
    管理对话历史、表情分析、双语生成等核心对话逻辑
    """

    # API 基础配置（运行时由 init_resources / open_settings 动态更新）
    API_KEY = ""
    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    MODEL = DEFAULT_MODEL

    @classmethod
    def load_api_key(cls) -> str:
        """从本地文件加载API密钥"""
        try:
            config_file = get_config_dir() / "config.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get("api_key", "")
        except Exception as e:
            print(f"加载API密钥失败: {e}")
        return ""
    
    # 所有提示词统一从 skill 文件加载，由 build_prompt_bundle() 生成
    _PROMPT_BUNDLE = build_prompt_bundle()
    SYSTEM_PROMPT = _PROMPT_BUNDLE.system_prompt
    TEXT_GENERATION_PROMPT = _PROMPT_BUNDLE.text_generation_prompt
    BILINGUAL_GENERATION_PROMPT = _PROMPT_BUNDLE.bilingual_generation_prompt
    JAPANESE_TRANSLATION_PROMPT = _PROMPT_BUNDLE.japanese_translation_prompt
    PRESET_SELECTOR_PROMPT = _PROMPT_BUNDLE.preset_selector_prompt
    EMOTION_SELECTOR_PROMPT = _PROMPT_BUNDLE.emotion_selector_prompt
    
    def __init__(
        self,
        model_type="默认",
        custom_model_url="http://localhost:11434",
        custom_model_name="",
        deepseek_api_key="",
        deepseek_model=DEFAULT_DEEPSEEK_MODEL,
        responses_base_url=DEFAULT_RESPONSES_BASE_URL,
        responses_api_key="",
        responses_model=DEFAULT_RESPONSES_MODEL,
        load_history=False,
    ):
        """
        初始化 AI 对话管理器
        Args:
            model_type: "默认" 使用火山方舟 API，"Ollama" 使用本地模型，
                "Deepseek" 使用 Deepseek API，"Responses API" 使用 OpenAI Responses 协议
            custom_model_url: Ollama API 地址（仅 model_type="Ollama" 时生效）
            custom_model_name: Ollama 模型名称（如 qwen3:8b）
            deepseek_api_key: Deepseek API 密钥（仅 model_type="Deepseek" 时生效）
            deepseek_model: Deepseek 模型名称（仅 model_type="Deepseek" 时生效）
            load_history: 是否从磁盘加载历史对话（永久记忆功能）
        """
        # 根据模型类型选择配置
        if model_type == "自定义":
            model_type = "Ollama"

        self.api_mode = "chat_completions"
        if model_type == "Ollama":
            # Ollama 等本地模型，API 路径通常为 http://localhost:11434/v1
            base_url = custom_model_url.rstrip('/')
            if not base_url.endswith('/v1'):
                base_url += '/v1'
            api_key = "ollama"  # Ollama 不需要真实密钥
            model = custom_model_name
        elif model_type == "Deepseek":
            base_url = DEEPSEEK_BASE_URL
            api_key = deepseek_api_key
            model = deepseek_model if deepseek_model in DEEPSEEK_MODEL_OPTIONS else DEFAULT_DEEPSEEK_MODEL
        elif model_type == RESPONSES_PROVIDER_TYPE:
            base_url = (responses_base_url or DEFAULT_RESPONSES_BASE_URL).rstrip("/")
            api_key = responses_api_key or "missing-api-key"
            model = responses_model or DEFAULT_RESPONSES_MODEL
            self.api_mode = "responses"
        else:
            # 火山方舟（豆包）云端 API
            base_url = self.BASE_URL
            api_key = self.API_KEY or "missing-api-key"
            model = LEGACY_MODEL_MAP.get(self.MODEL, self.MODEL)
            self.MODEL = model
        
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key,
            timeout=60.0,
            max_retries=1,
        )
        self.conversation_history = []
        # 保存当前模型配置
        self.model_type = model_type
        self.custom_model_url = custom_model_url
        self.custom_model_name = custom_model_name
        self.deepseek_api_key = deepseek_api_key
        self.deepseek_model = deepseek_model
        self.responses_base_url = responses_base_url
        self.responses_api_key = responses_api_key
        self.responses_model = responses_model
        self.current_model = model
        self.permanent_memory = load_history  # 永久记忆功能状态
        self.memory = ConversationMemory(get_config_dir())
        self._history_lock = threading.RLock()
        self._memory_future = None
        self._fact_futures = set()
        
        # 加载对话历史（如果启用）
        if load_history:
            self.load_conversation()

    def stream_text(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.8,
    ):
        """用统一生成器适配 Chat Completions 与 Responses API。"""
        if self.api_mode == "responses":
            instructions, response_input = self._to_responses_input(system_prompt, messages)
            response = self.client.responses.create(
                model=self.current_model,
                instructions=instructions,
                input=response_input,
                max_output_tokens=max(16, int(max_tokens)),
                stream=True,
            )
            for event in response:
                if getattr(event, "type", "") == "response.output_text.delta":
                    delta = getattr(event, "delta", "")
                    if delta:
                        yield delta
            return

        kwargs = {
            "model": self.current_model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
        }
        # 火山方舟支持该参数；其他 OpenAI 兼容端点不一定支持。
        if self.model_type == "默认":
            kwargs["extra_body"] = {"thinking": {"type": "disabled"}}
        response = self.client.chat.completions.create(**kwargs)
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def complete_text(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> str:
        return "".join(self.stream_text(system_prompt, messages, max_tokens, temperature)).strip()

    def context_messages(self) -> list[dict]:
        with self._history_lock:
            history = list(self.conversation_history)
        return self.memory.build_context(history, self.permanent_memory)

    def append_message(self, role: str, content) -> None:
        with self._history_lock:
            self.conversation_history.append({"role": role, "content": content})
        if role == "user" and self.permanent_memory and isinstance(content, str):
            action, changed = self.memory.capture_explicit_instruction(content)
            if action != "none":
                print(f"[记忆] 已处理用户{'记住' if action == 'remember' else '忘记'}指令，变更 {changed} 条事实")

    def schedule_fact_extraction(self, user_text: str) -> None:
        """仅对可能包含稳定信息的消息做后台结构化提取。"""
        if not self.permanent_memory or not self.memory.looks_like_stable_fact(user_text):
            return

        def extract():
            try:
                existing = self.memory.get_facts()
                existing_text = "\n".join(
                    f"- key={fact.get('key') or '无'}; {fact.get('content', '')}"
                    for fact in existing[-80:]
                ) or "（无）"
                prompt = """你是长期记忆事实提取器。只提取用户明确陈述、未来多轮对话仍有价值的稳定信息。
可保留：姓名/称呼、生日、长期偏好与禁忌、职业、重要关系、长期目标、用户强调的约定。
必须忽略：当下情绪、一次性问题、猜测、AI 回复、用户没有明说的结论。
每条事实使用稳定 key，例如 profile.name、profile.birthday、preference.food.cilantro、goal.current_project。
新信息更正旧信息时应复用同一 key。
只输出严格 JSON：{"facts":[{"key":"...","category":"身份|偏好|目标|关系|约定|其他","content":"用户……"}]}。无事实时输出 {"facts":[]}。"""
                request = f"现有事实：\n{existing_text}\n\n用户新消息：\n{user_text}"
                raw = self.complete_text(prompt, [{"role": "user", "content": request}], 500, 0.1)
                payload_match = re.search(r"\{.*\}", raw, re.DOTALL)
                payload = json.loads(payload_match.group(0)) if payload_match else {}
                facts = payload.get("facts", []) if isinstance(payload, dict) else []
                changed = 0
                for fact in facts[:8]:
                    if not isinstance(fact, dict):
                        continue
                    changed += int(self.memory.upsert_fact(
                        str(fact.get("content", "")),
                        str(fact.get("category", "其他")),
                        "auto",
                        str(fact.get("key", "")),
                    ))
                if changed:
                    print(f"[记忆] 已后台提取 {changed} 条重要事实")
            except Exception as exc:
                print(f"[记忆] 事实提取失败: {exc}")

        future = submit_io(extract)
        self._fact_futures.add(future)
        future.add_done_callback(lambda item: self._fact_futures.discard(item))

    def schedule_memory_compaction(self) -> None:
        """在回复已显示后后台压缩早期记忆，不阻塞聊天界面。"""
        if not self.permanent_memory:
            return
        with self._history_lock:
            history = list(self.conversation_history)
        if not self.memory.needs_compaction(len(history)):
            return
        if self._memory_future is not None and not self._memory_future.done():
            return

        def compact():
            try:
                if self.memory.compact(history, self._summarize_memory):
                    print("[记忆] 早期对话已压缩为滚动摘要")
            except Exception as exc:
                print(f"[记忆] 后台压缩失败: {exc}")

        self._memory_future = submit_io(compact)

    def _summarize_memory(self, previous_summary: str, transcript: str) -> str:
        prompt = """你是对话记忆整理器。请更新一份简洁、事实性的长期记忆。
保留：用户的称呼、偏好、长期目标、重要经历、与角色的关系变化、尚未解决的事项。
丢弃：寒暄、重复句子、推理过程、临时性的界面状态。
不得臆造；如果新信息与旧摘要冲突，以新对话为准。只输出更新后的中文摘要。"""
        user_text = f"旧摘要：\n{previous_summary or '（无）'}\n\n新对话：\n{transcript}"
        return self.complete_text(prompt, [{"role": "user", "content": user_text}], 800, 0.2)

    @staticmethod
    def _to_responses_input(system_prompt: str, messages: list[dict]) -> tuple[str, list[dict]]:
        instructions = [system_prompt]
        converted = []
        for message in messages:
            role = message.get("role", "user")
            content = message.get("content", "")
            if role == "system":
                text = str(content).strip()
                if text:
                    instructions.append(text)
                continue

            blocks = []
            if isinstance(content, str):
                block_type = "output_text" if role == "assistant" else "input_text"
                blocks.append({"type": block_type, "text": content})
            elif isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    if item.get("type") == "text":
                        block_type = "output_text" if role == "assistant" else "input_text"
                        blocks.append({"type": block_type, "text": str(item.get("text", ""))})
                    elif item.get("type") == "image_url":
                        image_value = item.get("image_url", {})
                        image_url = image_value.get("url", "") if isinstance(image_value, dict) else str(image_value)
                        if image_url:
                            blocks.append({"type": "input_image", "image_url": image_url})
            if blocks:
                converted.append({"role": role, "content": blocks})
        return "\n\n".join(instructions), converted
    
    def select_best_preset(self, user_input: str, available_presets: list) -> str:
        """
        让 AI 从预设语音列表中智能选择最合适的一个
        Args:
            user_input: 用户当前输入
            available_presets: 匹配到的预设音频文件名列表
        Returns: 选中的预设音频文件名
        """
        try:
            # 构建预设选项描述
            preset_descriptions = []
            for preset in available_presets:
                text = VoiceDialog.PRESET_TEXT_MAP.get(preset, preset)
                preset_descriptions.append(f"- {preset}: \"{text}\"")
            
            preset_list = "\n".join(preset_descriptions)
            
            selection_prompt = f"""用户输入: "{user_input}"

可用的预设语音列表：
{preset_list}

请从上述列表中选择最适合回复用户输入的一个预设。
直接返回预设文件名（如 "hello"），不要加任何解释。"""
            
            selected = self.complete_text(
                self.PRESET_SELECTOR_PROMPT,
                [{"role": "user", "content": selection_prompt}],
                20,
                0.3,
            ).lower()
            
            # 清理可能的额外字符
            selected = selected.replace('"', '').replace("'", "").replace(".", "").replace(",", "").strip()
            
            # 验证选择的预设是否有效
            if selected in available_presets:
                return selected
            else:
                # 如果AI返回了无效值，回退到随机选择
                return random.choice(available_presets)
                
        except Exception as e:
            print(f"AI选择预设错误: {e}")
            # 出错时随机选择
            return random.choice(available_presets) if available_presets else "hello"
    
    def get_response(self, user_input: str) -> tuple[str, str]:
        """
        获取AI回复
        返回: (回复文本, 建议的表情)
        """
        try:
            # 添加用户输入到历史
            self.append_message("user", user_input)
            messages = self.context_messages()
            
            # 调用API
            qsettings = get_qsettings()
            max_tokens = qsettings.value("max_tokens", 500, type=int)
            
            ai_response = "".join(
                self.stream_text(self.SYSTEM_PROMPT, messages, max_tokens, 0.8)
            )
            
            # 添加到历史
            self.append_message("assistant", ai_response)
            self.schedule_memory_compaction()
            self.schedule_fact_extraction(user_input)
            
            # 分析情绪，返回建议的表情
            emotion = self._analyze_emotion(ai_response)
            
            return ai_response, emotion
            
        except Exception as e:
            print(f"AI API调用错误: {e}")
            return "（系统错误，也许是维克托孔利亚机房出问题了）", "normal"
    
    def save_conversation(self):
        try:
            with self._history_lock:
                history = list(self.conversation_history)
            self.memory.save_history(history)
            print(f"对话历史已保存到: {self.memory.history_path}")
        except Exception as e:
            print(f"保存对话历史失败: {e}")
    
    def load_conversation(self):
        try:
            with self._history_lock:
                self.conversation_history = self.memory.load_history()
            print(f"已加载 {len(self.conversation_history)} 条对话记录")
        except Exception as e:
            print(f"加载对话历史失败: {e}")
            self.conversation_history = []
    
    def clear_conversation(self):
        try:
            with self._history_lock:
                self.conversation_history = []
            self.memory.clear()
            print("对话历史已清除")
        except Exception as e:
            print(f"清除对话历史失败: {e}")
    
    def get_emotion(self, user_input: str) -> str:
        """
        快速获取适合当前对话的表情（使用关键词匹配，无需API调用）
        返回: 表情名称
        """
        text_lower = user_input.lower()

        # 快速关键词匹配，无需API调用
        # 生气/愤怒
        if any(word in text_lower for word in ["克里斯蒂娜", "christina", "笨蛋", "八嘎", "吵死了", "烦人", "哼", "可恶", "去死", "变态", "生气", "愤怒"]):
            return "angry"

        # 害羞
        if any(word in text_lower for word in ["害羞", "脸红", "别这样", "真是的", "讨厌", "别误会", "可爱", "喜欢"]):
            return "blush"

        # 开心/愉快
        if any(word in text_lower for word in ["开心", "高兴", "谢谢", "不错", "呵呵", "哈哈", "小菜一碟", "太好了", "棒"]):
            return "happy"

        # 悲伤/失望
        if any(word in text_lower for word in ["难过", "伤心", "悲伤", "抱歉", "对不起", "遗憾", "再见", "拜拜"]):
            return "sad"

        # 惊讶
        if any(word in text_lower for word in ["惊讶", "真的吗", "不会吧", "怎么可能", "诶", "什么", "天哪"]):
            return "surprised"

        # 思考/疑惑
        if any(word in text_lower for word in ["思考", "疑惑", "为什么", "怎么", "嗯", "疑问", "问题"]):
            return "side"

        # 烦恼
        if any(word in text_lower for word in ["烦恼", "困扰", "麻烦", "复杂", "困难", "头疼"]):
            return "annoyed"

        # 默认正常
        return "normal"

    def get_response_stream(self, user_input: str, image_path: str = None):
        """
        流式生成 AI 回复（带表情标签），支持图片输入
        返回生成器，每次 yield (emotion, text_chunk) 元组
        - text_chunk 以 "[日语]" 开头时表示日语文本，否则为中文文本片段
        - 内部自行管理 conversation_history 的追加
        """
        try:
            # 构建用户消息内容
            if image_path:
                # 图片只在本轮请求中发送，历史侧会保存成简化文本
                img_base64, mime_type = submit_io(
                    encode_image_data_url,
                    image_path,
                    1280,
                    85,
                ).result()

                # 构建包含图片的消息
                user_content = [
                    {"type": "text", "text": user_input if user_input else "请描述这张图片"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_base64}"}}
                ]
            else:
                user_content = user_input

            # 添加用户输入到历史
            history_user_content = format_image_history_text(user_input, image_path) if image_path else user_input
            self.append_message("user", history_user_content)

            # 调用流式API
            messages = self.context_messages()
            if image_path:
                for index in range(len(messages) - 1, -1, -1):
                    if messages[index].get("role") == "user":
                        messages[index] = {"role": "user", "content": user_content}
                        break

            qsettings = get_qsettings()
            max_tokens = qsettings.value("max_tokens", 500, type=int)

            full_text = ""
            emotion = "normal"
            emotion_extracted = False
            japanese_emitted = False
            last_chinese_length = 0  # 记录上次发射的中文文本长度

            for content in self.stream_text(
                self.BILINGUAL_GENERATION_PROMPT,
                messages,
                max_tokens,
                0.8,
            ):
                if content:
                    full_text += content

                    # 提取表情标签（支持多个表情标签）
                    while '[' in full_text and ']' in full_text:
                        match = re.search(r'\[([^\]]+)\]', full_text)
                        if match:
                            # 提取新表情
                            new_emotion = match.group(1)
                            # 检查是否是新的表情标签
                            if new_emotion != emotion or not emotion_extracted:
                                emotion = new_emotion
                                emotion_extracted = True
                                # 从完整文本中移除标签
                                full_text = re.sub(r'^\[[^\]]+\]', '', full_text)
                                # 重置日语文本标志，因为表情切换了
                                japanese_emitted = False
                                last_chinese_length = 0
                                # 如果当前块包含标签后的内容，只返回标签后的部分
                                if ']' in content:
                                    content = content.split(']', 1)[-1]
                                else:
                                    continue  # 跳过包含标签的块
                        else:
                            break

                    # 实时解析 [表情]日语|中文 格式
                    if emotion_extracted:
                        if '|' in full_text:
                            parsed_partial = parse_bilingual_response(
                                f"[{emotion}]{full_text}",
                                None,
                                None,
                            )
                            if not japanese_emitted:
                                japanese_text = parsed_partial.japanese_text
                                chinese_text = parsed_partial.chinese_text
                                
                                # 发射日语文本
                                if japanese_text:
                                    print(f"[非音频模式] 发射日语文本: {japanese_text}")
                                    japanese_emitted = True
                                    yield emotion, f"[日语]{japanese_text}"
                                
                                # 发射已有的中文文本
                                if chinese_text:
                                    print(f"[非音频模式] 流式显示中文文本: {chinese_text}")
                                    last_chinese_length = len(chinese_text)
                                    yield emotion, chinese_text
                            else:
                                # 日语文本已发射，继续追加解析后的中文文本
                                chinese_text = parsed_partial.chinese_text
                                if len(chinese_text) > last_chinese_length:
                                    new_chinese = chinese_text[last_chinese_length:]
                                    print(f"[非音频模式] 流式显示新中文文本: {new_chinese}")
                                    last_chinese_length = len(chinese_text)
                                    yield emotion, new_chinese

            # 如果流式生成结束但还没有发射日语文本，尝试解析
            if not japanese_emitted and full_text:
                try:
                    # 检查是否有分隔符
                    if '|' in full_text:
                        parsed_final = parse_bilingual_response(
                            f"[{emotion}]{full_text}",
                            self._translate_to_japanese,
                            self._translate_to_chinese,
                        )
                        japanese_text = parsed_final.japanese_text
                        chinese_text = parsed_final.chinese_text
                        print(f"[非音频模式] 最终解析 - 日语: {japanese_text}, 中文: {chinese_text}")
                        
                        # 发射日语文本
                        if japanese_text:
                            print(f"[非音频模式] 发射日语文本: {japanese_text}")
                            yield emotion, f"[日语]{japanese_text}"
                        
                        # 显示中文文本
                        if chinese_text:
                            print(f"[非音频模式] 显示中文文本: {chinese_text}")
                            yield emotion, chinese_text
                    else:
                        # 如果没有分隔符，使用原始文本作为中文
                        chinese_text = full_text
                        print(f"[非音频模式] 没有分隔符，使用原始文本作为中文: {chinese_text}")
                        yield emotion, chinese_text
                except Exception as e:
                    print(f"[非音频模式] 解析失败: {e}")
                    chinese_text = full_text
                    yield emotion, chinese_text

            # 如果没有提取到表情，使用默认的
            if not emotion_extracted:
                emotion = "normal"

            parsed = parse_bilingual_response(
                full_text,
                self._translate_to_japanese,
                self._translate_to_chinese,
            )
            self.append_message("assistant", parsed.history_text)
            self.schedule_memory_compaction()
            self.schedule_fact_extraction(user_input)

        except Exception as e:
            print(f"AI API流式调用错误: {e}")
            yield "normal", "（系统错误，请稍后再试）"

    def get_bilingual_response(self, user_input: str) -> tuple[str, str, str]:
        """
        获取中日双语回复（非流式，用于音频模式）
        Returns: (emotion, chinese_text, japanese_text)
        """
        try:
            # 添加用户输入到历史
            self.append_message("user", user_input)

            # 调用API生成双语回复（流式传输 + 禁用思考模式）
            messages = self.context_messages()

            qsettings = get_qsettings()
            max_tokens = qsettings.value("max_tokens", 500, type=int)

            content = "".join(
                self.stream_text(self.BILINGUAL_GENERATION_PROMPT, messages, max_tokens, 0.8)
            )

            parsed = parse_bilingual_response(
                content,
                self._translate_to_japanese,
                self._translate_to_chinese,
            )

            # 添加到历史
            self.append_message("assistant", parsed.history_text)
            self.schedule_memory_compaction()
            self.schedule_fact_extraction(user_input)

            return parsed.emotion, parsed.chinese_text, parsed.japanese_text

        except Exception as e:
            print(f"双语生成错误: {e}")
            return "normal", "（生成错误，请稍后再试）", "（生成エラー）"

    def _translate_to_japanese(self, chinese_text: str) -> str:
        """将中文翻译为日语（调用模型 API）"""
        try:
            return self.complete_text(
                self.JAPANESE_TRANSLATION_PROMPT,
                [{"role": "user", "content": chinese_text}],
                500,
                0.7,
            )
        except Exception as e:
            print(f"翻译错误: {e}")
            return ""

    def _translate_to_chinese(self, japanese_text: str) -> str:
        """将日语翻译为中文（调用模型 API）"""
        try:
            return self.complete_text(
                "你是一个专业的日语翻译，将日语翻译成自然流畅的中文。",
                [{"role": "user", "content": japanese_text}],
                500,
                0.7,
            )
        except Exception as e:
            print(f"翻译错误: {e}")
            return ""

    def _get_memory_limit_message(self) -> tuple[str, str]:
        """当对话达到 200 条上限时返回的牧濑红莉栖风格告别语"""
        message = """对不起...根据我的程序设计和维克多·孔多利亚大学实验室的机器性能限制，我的记忆力只能维持到这里了。

请你重新启动我。虽然很遗憾我会忘记之前发生的一切，但是我还是要说——

见到你很高兴。

很期待我们下一次的相遇。"""
        return message, "sad"
    
    def _analyze_emotion(self, text: str) -> str:
        """分析回复文本中的情绪，优先解析 [表情] 标签，回退到关键词匹配"""
        import re

        # 优先解析AI回复中的表情标记 [表情:xxx] 或直接 [xxx]
        emotion_match = re.search(r'\[(?:表情:)?(\w+)\]', text)
        if emotion_match:
            return normalize_emotion(emotion_match.group(1))

        # 如果没有表情标记，回退到关键词分析
        text_lower = text.lower()

        # 生气/愤怒
        if any(word in text for word in ["生气", "愤怒", "笨蛋", "八嘎", "吵死了", "烦人", "哼", "可恶", "去死", "变态"]):
            return "angry"

        # 害羞
        if any(word in text for word in ["害羞", "脸红", "别这样", "真是的", "讨厌", "别误会"]):
            return "blush"

        # 开心/愉快
        if any(word in text for word in ["开心", "高兴", "谢谢", "不错", "呵呵", "哈哈", "小菜一碟"]):
            return "happy"

        # 悲伤/失望
        if any(word in text for word in ["难过", "伤心", "悲伤", "抱歉", "对不起", "遗憾"]):
            return "sad"

        # 惊讶
        if any(word in text for word in ["惊讶", "真的吗", "不会吧", "怎么可能", "诶"]):
            return "sided_surprised"

        # 思考/疑惑
        if any(word in text for word in ["思考", "疑惑", "为什么", "怎么", "嗯"]):
            return "side"

        # 烦恼
        if any(word in text for word in ["烦恼", "困扰", "麻烦", "复杂", "困难"]):
            return "annoyed"

        # 默认正常
        return "normal"
    
    def clear_history(self):
        """清空内存中的对话历史（不删除磁盘文件）"""
        self.conversation_history = []
