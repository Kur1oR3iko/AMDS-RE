"""
AI 回复解析器
负责解析 AI 返回的 "[表情]日语|中文" 格式文本，
提取表情标签、分割日语/中文内容，以及清理对话历史用于持久化存储
"""

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable


# ── 表情相关 ──────────────────────────────────────────────

# 所有合法的表情名称（对应图片文件名中的表情部分）
VALID_EMOTIONS = {
    "normal",
    "angry",
    "sided_angry",
    "blush",
    "sided_blush",
    "happy",
    "sad",
    "surprised",
    "sided_surprised",
    "side",
    "sided_thinking",
    "annoyed",
    "sided_worried",
    "eyes_closed",
    "sided_eyes_closed",
    "sided_pleasant",
    "disappointed",
    "indifferent",
    "pissed",
    "winking",
}

# 非标准表情名到标准表情名的映射（兼容 AI 输出的各种变体）
EMOTION_ALIASES = {
    "表情:normal": "normal",
    "表情:angry": "angry",
    "表情:happy": "happy",
    "表情:blush": "blush",
    "表情:sad": "sad",
    "表情:surprised": "sided_surprised",
    "surprised": "sided_surprised",
    "thinking": "sided_thinking",
    "worried": "sided_worried",
}


# ── 数据结构 ──────────────────────────────────────────────

@dataclass
class ParsedReply:
    """解析后的 AI 回复结构"""
    emotion: str           # 表情名称
    japanese_text: str     # 日语文本
    chinese_text: str      # 中文文本

    @property
    def history_text(self) -> str:
        """用于存入对话历史的文本（优先中文）"""
        return self.chinese_text or self.japanese_text


# ── 公开 API ──────────────────────────────────────────────

def normalize_emotion(emotion: str | None) -> str:
    """将表情名标准化，无效值回退为 'normal'"""
    if not emotion:
        return "normal"
    normalized = emotion.strip().lower()
    normalized = EMOTION_ALIASES.get(normalized, normalized)
    return normalized if normalized in VALID_EMOTIONS else "normal"


def parse_bilingual_response(
    raw_text: str,
    translate_to_japanese: Callable[[str], str] | None = None,
    translate_to_chinese: Callable[[str], str] | None = None,
) -> ParsedReply:
    """
    解析 AI 返回的双语回复文本
    支持格式: "[表情]日语|中文"，可多行
    如果只有单语，会使用翻译回调函数补充另一种语言
    """
    text = (raw_text or "").strip()
    emotion = _extract_emotion(text)
    text = re.sub(r"\[[^\]]+\]", "", text).strip()  # 移除所有表情标签

    japanese_parts: list[str] = []
    chinese_parts: list[str] = []

    for segment in _split_segments(text):
        if "|" in segment:
            # 用竖线分隔的双语段落
            japanese, chinese = segment.split("|", 1)
            _append_nonempty(japanese_parts, _clean_display_text(japanese))
            _append_nonempty(chinese_parts, _clean_display_text(chinese))
        elif _looks_japanese(segment):
            _append_nonempty(japanese_parts, _clean_display_text(segment))
        else:
            _append_nonempty(chinese_parts, _clean_display_text(segment))

    japanese_text = "\n".join(japanese_parts).strip()
    chinese_text = "\n".join(chinese_parts).strip()

    # 单语时调用翻译回调补充
    if chinese_text and not japanese_text and translate_to_japanese:
        japanese_text = translate_to_japanese(chinese_text).strip()
    elif japanese_text and not chinese_text and translate_to_chinese:
        chinese_text = translate_to_chinese(japanese_text).strip()

    # 都为空时使用原始文本
    if not chinese_text and not japanese_text:
        chinese_text = text

    return ParsedReply(emotion=emotion, japanese_text=japanese_text, chinese_text=chinese_text)


def format_image_history_text(text: str, image_path: str | None) -> str:
    """将带图片的消息格式化为纯文本表示，用于对话历史存储"""
    caption = (text or "").strip() or "请描述这张图片"
    if not image_path:
        return caption
    return f"{caption}\n[图片: {Path(image_path).name}]"


def history_content_to_text(content) -> str:
    """
    将对话历史中的 content 字段转为纯文本
    content 可能是字符串或包含图片的 OpenAI 多模态消息列表
    """
    if isinstance(content, str):
        # 脱敏 base64 图片数据
        return re.sub(r"data:image/[^;]+;base64,[A-Za-z0-9+/=]+", "[图片]", content)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, dict) and item.get("type") == "image_url":
                parts.append("[图片]")
        return "\n".join(part for part in parts if part).strip()
    return str(content)


def sanitize_history_messages(messages: Iterable[dict]) -> list[dict]:
    """
    清理对话历史消息，确保每条消息格式正确且 content 为纯文本
    用于保存到磁盘前过滤掉 base64 图片等大数据
    """
    sanitized = []
    for message in messages or []:
        if not isinstance(message, dict):
            continue
        role = message.get("role")
        if role not in {"user", "assistant", "system"}:
            continue
        sanitized.append({
            "role": role,
            "content": history_content_to_text(message.get("content", "")),
        })
    return sanitized


def extract_emotions(text: str) -> list[str]:
    """Extract valid emotion control tags from any position in text."""
    emotions = []
    for match in re.findall(r"\[([^\]]+)\]", text or ""):
        emotion = normalize_emotion(match)
        if emotion != "normal" or match.strip().lower() == "normal":
            emotions.append(emotion)
    return emotions


def clean_stream_display_text(text: str) -> str:
    """移除完整或破碎的表情控制标签，避免控制符显示到聊天框。"""
    return _clean_display_text(text)


# ── 内部辅助函数 ──────────────────────────────────────────

def _extract_emotion(text: str) -> str:
    """从文本中提取最后一个合法的表情标签"""
    matches = re.findall(r"\[([^\]]+)\]", text or "")
    for match in reversed(matches):
        emotion = normalize_emotion(match)
        if emotion != "normal" or match.strip().lower() == "normal":
            return emotion
    return "normal"


def _split_segments(text: str) -> list[str]:
    """将文本按空行或表情标签位置拆分为多个段落"""
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    parts = re.split(r"\n+|(?=\[[^\]]+\])", normalized)
    return [part.strip() for part in parts if part.strip()]


def _clean_display_text(text: str) -> str:
    cleaned = re.sub(r"\[[^\]]+\]", "", text or "")
    cleaned = re.sub(r"\[[A-Za-z_:\u4e00-\u9fff]*$", "", cleaned)
    return cleaned.strip()


def _append_nonempty(target: list[str], value: str) -> None:
    """追加非空字符串到列表"""
    cleaned = value.strip()
    if cleaned:
        target.append(cleaned)


def _looks_japanese(text: str) -> bool:
    """检测文本是否包含日语字符（平假名/片假名/半角片假名）"""
    return bool(re.search(r"[\u3040-\u30ff\uff66-\uff9f]", text or ""))
