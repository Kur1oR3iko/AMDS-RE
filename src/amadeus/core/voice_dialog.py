"""
语音对话管理模块 - 支持中英文关键词
"""
import random
from typing import List, Optional

from ..constants import VOICE_RESPONSES, PRESET_TEXT_MAP, AUDIO_EMOTION_MAP


class VoiceDialog:
    """语音对话管理器 - 支持中英文关键词"""
    
    RESPONSES = VOICE_RESPONSES
    
    _recent_responses = {}
    _MAX_RECENT = 3
    
    @classmethod
    def get_response(cls, text: str) -> str:
        """根据输入文本获取语音响应 - 支持中英文"""
        text_lower = text.lower()
        
        for keyword, responses in cls.RESPONSES.items():
            if keyword in text_lower:
                recent = cls._recent_responses.get(keyword, [])
                available_responses = [r for r in responses if r not in recent]
                if not available_responses:
                    available_responses = responses
                selected = random.choice(available_responses)
                recent.append(selected)
                if len(recent) > cls._MAX_RECENT:
                    recent.pop(0)
                cls._recent_responses[keyword] = recent
                return selected
        
        recent = cls._recent_responses.get("default", [])
        available_responses = [r for r in cls.RESPONSES["default"] if r not in recent]
        if not available_responses:
            available_responses = cls.RESPONSES["default"]
        selected = random.choice(available_responses)
        recent.append(selected)
        if len(recent) > cls._MAX_RECENT:
            recent.pop(0)
        cls._recent_responses["default"] = recent
        return selected
    
    @classmethod
    def get_random_greeting(cls) -> str:
        """获取随机问候语"""
        greetings = ["hello", "nice_to_meet_okabe", "pleased_to_meet_you"]
        return random.choice(greetings)
    
    @classmethod
    def get_all_matching_responses(cls, text: str) -> list:
        """获取所有匹配的预设响应列表"""
        text_lower = text.lower()
        matching = []
        
        for keyword, responses in cls.RESPONSES.items():
            if keyword in text_lower and keyword != "default":
                recent = cls._recent_responses.get(keyword, [])
                available_responses = [r for r in responses if r not in recent]
                if not available_responses:
                    available_responses = responses
                matching.extend(available_responses)
        
        if not matching:
            recent = cls._recent_responses.get("default", [])
            available_responses = [r for r in cls.RESPONSES["default"] if r not in recent]
            if not available_responses:
                available_responses = cls.RESPONSES["default"]
            matching.extend(available_responses)
        
        return matching
    
    @classmethod
    def get_emotion_for_audio(cls, audio_name: str) -> str:
        """根据语音文件名获取对应的表情"""
        return AUDIO_EMOTION_MAP.get(audio_name, "normal")
    
    @classmethod
    def get_preset_text(cls, audio_name: str) -> str:
        """获取预设语音对应的文本"""
        return PRESET_TEXT_MAP.get(audio_name, audio_name)
