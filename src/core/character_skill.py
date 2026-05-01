"""角色 skill 加载与系统提示词生成。"""

from dataclasses import dataclass

from core.resources import PROMPTS_DIR


DEFAULT_SKILL_FILE = "kurisu_amadeus_skill.md"


@dataclass(frozen=True)
class CharacterPromptBundle:
    """AI 对话系统使用的一组角色提示词。"""

    system_prompt: str
    text_generation_prompt: str
    bilingual_generation_prompt: str
    japanese_translation_prompt: str
    preset_selector_prompt: str
    emotion_selector_prompt: str


def load_character_skill(filename: str = DEFAULT_SKILL_FILE) -> str:
    """读取项目内角色 skill，失败时返回保底设定。"""
    skill_path = PROMPTS_DIR / filename
    try:
        if skill_path.exists():
            return skill_path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        print(f"加载角色 skill 失败: {exc}")

    return """# Amadeus 牧濑红莉栖角色 Skill
你是《命运石之门》中的牧濑红莉栖。保持理性、傲娇、嘴硬心软的语气。
常规回复必须输出：[表情]日语|中文。"""


def build_prompt_bundle(skill_text: str | None = None) -> CharacterPromptBundle:
    """根据角色 skill 生成各场景使用的系统提示词。"""
    skill = skill_text or load_character_skill()
    valid_emotions = (
        "normal, angry, sided_angry, blush, sided_blush, happy, sad, surprised, "
        "sided_surprised, side, sided_thinking, annoyed, sided_worried, eyes_closed, "
        "sided_eyes_closed, sided_pleasant, disappointed, indifferent, pissed, winking"
    )

    system_prompt = f"""{skill}

当前任务：作为 AMDS 中的牧濑红莉栖与用户对话。
使用第一人称“我”，不要跳出角色，不要做旁白式解释。"""

    bilingual_prompt = f"""{skill}

当前任务：生成 AMDS 可解析的中日双语回复。

硬性输出规则：
- 只输出「[表情]日语|中文」内容，不要输出任何解释。
- 表情必须从以下列表选择：{valid_emotions}
- 表情标签可以自然出现在段落开头、中间或结尾，但必须是 `[表情名]`。
- 日语必须是纯日语，中文必须是纯中文，两者用半角竖线 `|` 分隔。
- 如果分多段，每段都继续使用「[表情]日语|中文」格式。"""

    text_generation_prompt = f"""{skill}

当前任务：生成中文聊天文本，可携带 `[表情名]` 控制标签。
要求：保持红莉栖人格；回复简洁；表情必须从以下列表选择：{valid_emotions}。"""

    japanese_translation_prompt = f"""{skill}

当前任务：把用户给出的中文翻译成自然日语。
要求：
- 保留牧濑红莉栖式的理性、傲娇、女性化语气。
- 只输出日语译文，不要解释。

中文文本："""

    preset_selector_prompt = f"""{skill}

当前任务：从给定的预设音频文件名列表中选择最适合回应用户输入的一项。
规则：
- 只能从候选列表选择，不能创造新文件名。
- 优先语义相关，其次情绪匹配，再考虑角色一致性。
- 只返回文件名，不要解释、标点或引号。"""

    emotion_selector_prompt = f"""{skill}

当前任务：根据用户输入和上下文选择一个最合适的表情。
可选表情：{valid_emotions}
只返回表情名，不要解释。"""

    return CharacterPromptBundle(
        system_prompt=system_prompt,
        text_generation_prompt=text_generation_prompt,
        bilingual_generation_prompt=bilingual_prompt,
        japanese_translation_prompt=japanese_translation_prompt,
        preset_selector_prompt=preset_selector_prompt,
        emotion_selector_prompt=emotion_selector_prompt,
    )
