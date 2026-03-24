"""
表情相关常量
"""

VALID_EMOTIONS = [
    "normal", "happy", "angry", "sad", "blush", "annoyed",
    "disappointed", "eyes_closed", "indifferent", "pissed", "side",
    "sided_angry", "sided_blush", "sided_eyes_closed", "sided_pleasant",
    "sided_surprised", "sided_thinking", "sided_worried", "winking"
]

AUDIO_EMOTION_MAP = {
    "hello": "happy",
    "nice_to_meet_okabe": "happy",
    "pleased_to_meet_you": "happy",
    "look_forward_to_working": "happy",
    "heheh": "happy",
    "nice": "happy",
    "happy": "happy",
    "ok": "happy",
    "ask_me_whatever": "happy",

    "christina": "angry",
    "dont_call_me_like_that": "angry",
    "dont_add_tina": "angry",
    "who_the_hell_christina": "angry",
    "why_christina": "angry",
    "angry": "angry",
    "pissed": "angry",
    "gah": "angry",
    "gah_extended": "angry",
    "daga_kotowaru": "angry",
    "sided_angry": "angry",

    "blush": "blush",
    "sided_blush": "blush",
    "dont_look_at_me": "blush",

    "annoyed": "annoyed",
    "what_do_you_want": "annoyed",
    "sounds_tough": "annoyed",
    "devilish_pervert": "annoyed",

    "disappointed": "disappointed",
    "sorry": "disappointed",
    "sad": "sad",

    "eyes_closed": "eyes_closed",
    "sided_eyes_closed": "eyes_closed",
    "i_see": "eyes_closed",
    "i_guess": "eyes_closed",

    "indifferent": "indifferent",
    "tm_nonsense": "indifferent",
    "tm_not_possible": "indifferent",
    "humans_software": "indifferent",

    "side": "side",
    "sided_thinking": "side",
    "sided_worried": "side",
    "memory_complex": "side",
    "modifying_memories_impossible": "side",

    "sided_surprised": "sided_surprised",
    "huh_why_say": "sided_surprised",

    "sided_pleasant": "sided_pleasant",
    "could_i_help": "sided_pleasant",

    "winking": "winking",
    "you_sure": "winking",

    "default": "normal"
}

EMOTION_DISPLAY_NAMES = {
    "normal": "正常",
    "happy": "开心",
    "angry": "生气",
    "sad": "悲伤",
    "blush": "害羞",
    "annoyed": "烦恼",
    "disappointed": "失望",
    "eyes_closed": "闭眼",
    "indifferent": "冷淡",
    "pissed": "愤怒",
    "side": "侧脸",
    "sided_angry": "侧面生气",
    "sided_blush": "侧面害羞",
    "sided_eyes_closed": "侧面闭眼",
    "sided_pleasant": "侧面愉悦",
    "sided_surprised": "侧面惊讶",
    "sided_thinking": "侧面思考",
    "sided_worried": "侧面担忧",
    "winking": "眨眼"
}
