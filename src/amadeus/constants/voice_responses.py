"""
语音响应相关常量
"""

VOICE_RESPONSES = {
    "hello": ["hello", "nice_to_meet_okabe", "pleased_to_meet_you"],
    "hi": ["hello", "nice_to_meet_okabe"],
    "你好": ["hello", "nice_to_meet_okabe", "pleased_to_meet_you"],
    "您好": ["hello", "pleased_to_meet_you"],
    "在吗": ["what_is_it", "hello"],

    "christina": ["christina", "dont_call_me_like_that", "dont_add_tina", "who_the_hell_christina", "why_christina"],
    "克里斯蒂娜": ["christina", "dont_call_me_like_that", "dont_add_tina", "who_the_hell_christina", "why_christina"],

    "help": ["could_i_help", "what_do_you_want", "ask_me_whatever"],
    "帮助": ["could_i_help", "ask_me_whatever"],
    "帮我": ["could_i_help", "what_do_you_want"],
    "做什么": ["what_do_you_want", "ask_me_whatever"],
    "能做什么": ["could_i_help", "ask_me_whatever"],

    "sorry": ["sorry", "i_guess", "i_see"],
    "对不起": ["sorry", "i_guess"],
    "抱歉": ["sorry", "i_see"],
    "不好意思": ["sorry"],

    "ok": ["ok", "nice", "heheh"],
    "好的": ["ok", "nice"],
    "知道了": ["ok", "i_see"],
    "明白": ["ok", "i_see"],
    "是": ["ok", "nice"],
    "对": ["ok", "nice"],

    "time": ["tm_you_said", "tm_too_early", "tm_nonsense"],
    "时间": ["tm_you_said", "tm_too_early"],
    "几点": ["tm_you_said"],
    "什么时候": ["tm_you_said", "tm_too_early"],

    "memory": ["memory_complex", "modifying_memories_impossible", "memories_christina"],
    "记忆": ["memory_complex", "modifying_memories_impossible", "memories_christina"],
    "忘记": ["memory_complex", "modifying_memories_impossible"],
    "记得": ["memory_complex", "memories_christina"],

    "pervert": ["pervert_confirmed", "perverts_go_to_hell", "pervert_idot_wanttodie", "devilish_pervert"],
    "变态": ["pervert_confirmed", "perverts_go_to_hell", "pervert_idot_wanttodie"],
    "色狼": ["pervert_confirmed", "devilish_pervert"],
    "讨厌": ["pervert_confirmed", "gah"],

    "senpai": ["senpai_question", "senpai_please_dont_tell", "uh_senpai", "senpai_who_is_this"],
    "前辈": ["senpai_question", "uh_senpai", "senpai_who_is_this"],
    "学长": ["senpai_question", "senpai_please_dont_tell"],
    "学姐": ["senpai_question"],

    "开心": ["happy", "heheh", "nice"],
    "高兴": ["happy", "heheh"],
    "难过": ["sorry", "sounds_tough"],
    "伤心": ["sorry", "sad"],
    "生气": ["angry", "gah"],
    "愤怒": ["angry", "pissed"],

    "为什么": ["huh_why_say", "you_sure"],
    "怎么": ["huh_why_say", "what_is_it"],
    "什么": ["what_is_it", "what_do_you_want"],
    "谁": ["who_the_hell_christina", "senpai_who_is_this"],

    "谢谢": ["nice", "ok", "heheh"],
    "感谢": ["nice", "pleased_to_meet_you"],

    "再见": ["nice_to_meet_okabe", "look_forward_to_working"],
    "拜拜": ["nice_to_meet_okabe"],
    "晚安": ["nice_to_meet_okabe", "look_forward_to_working"],

    "default": ["what_is_it", "huh_why_say", "you_sure", "sounds_tough", "humans_software"]
}

PRESET_TEXT_MAP = {
    "hello": "你好。",
    "nice_to_meet_okabe": "很高兴见到你，冈部。",
    "pleased_to_meet_you": "很高兴认识你。",
    "look_forward_to_working": "期待与你合作。",

    "christina": "我说了不要叫我克里斯蒂娜！",
    "dont_call_me_like_that": "不要那样叫我！",
    "dont_add_tina": "不要加蒂娜！",
    "who_the_hell_christina": "谁是克里斯蒂娜啊！",
    "why_christina": "为什么是克里斯蒂娜？",
    "memories_christina": "克里斯蒂娜的记忆...",
    "should_christina": "应该叫克里斯蒂娜吗...",

    "could_i_help": "有什么我可以帮忙的吗？",
    "what_do_you_want": "你想要什么？",
    "ask_me_whatever": "尽管问吧。",
    "what_is_it": "什么事？",

    "sorry": "对不起。",
    "i_guess": "我想是吧。",
    "i_see": "我明白了。",
    "ok": "好的。",
    "nice": "不错。",
    "heheh": "呵呵。",
    "you_sure": "你确定吗？",
    "still_not_happy": "还是不太高兴。",

    "huh_why_say": "嗯？为什么这么说？",
    "sounds_tough": "听起来很困难。",
    "humans_software": "人类就像软件一样。",

    "memory_complex": "记忆是很复杂的。",
    "modifying_memories_impossible": "修改记忆是不可能的。",
    "secret_diary": "秘密日记...",

    "pervert_confirmed": "确认是变态。",
    "perverts_go_to_hell": "变态去死吧！",
    "pervert_idot_wanttodie": "你这个变态白痴，想死吗？",
    "devilish_pervert": "恶魔般的变态。",

    "senpai_question": "前辈？",
    "senpai_please_dont_tell": "前辈，请不要告诉别人...",
    "uh_senpai": "呃，前辈...",
    "senpai_who_is_this": "前辈，这是谁？",
    "senpai_questionmark": "前辈？",

    "happy": "开心~",
    "sad": "难过...",
    "angry": "生气！",
    "pissed": "愤怒！",
    "gah": "啊！",
    "gah_extended": "啊——！",
    "blush": "（脸红）",

    "tm_you_said": "时间机器的话...你是说...",
    "tm_too_early": "时间机器那种东西还太早了。",
    "tm_nonsense": "胡说八道。",
    "tm_not_possible": "那是不可能的。",
    "tm_we_dont_know": "我们不知道。",
    "tm_scientist_no_evidence": "科学家没有证据。",
    "tm_you_said": "你说过...",

    "daga_kotowaru": "但是我拒绝。",
    "nice_to_meet_okabe": "很高兴见到你，冈部。",
    "tone": "叮~",

    "whats_so_funny_senpai": "前辈，有什么好笑的？",
    "this_guy_hopeless": "这家伙没救了。",
    "leskinen_awesome": "太棒了！",
    "leskinen_holy_cow": "天哪！",
    "leskinen_nice": "不错！",
    "leskinen_oh_no": "哦不！",
    "leskinen_shaman": "萨满...",

    "ringtone_beginning_of_fight": "[铃声] 战斗的开始",
    "ringtone_easygoingness": "[铃声] 悠闲",
    "ringtone_gate_of_steiner": "[铃声] 斯坦因之门",
    "ringtone_over_the_sky": "[铃声] 天空之上",
    "ringtone_precaution": "[铃声] 预防",
    "ringtone_reunion": "[铃声] 重逢",
    "ringtone_village": "[铃声] 村庄",
}
