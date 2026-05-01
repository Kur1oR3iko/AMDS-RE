"""
预设语音匹配与表情映射
管理用户输入关键词 → 预设音频文件的映射关系，
以及音频文件名 → 角色表情的映射关系
所有预设音频均从原版 Amadeus 手机应用中解包提取
"""

import random


class VoiceDialog:
    """
    语音对话管理器
    根据用户输入的中英文关键词匹配预设语音，并避免短时间内重复选择同一条
    """

    # 中英文关键词 → 可匹配的预设音频文件名列表（不含 .ogg 后缀）
    RESPONSES = {
        # 问候语
        "hello": ["hello", "nice_to_meet_okabe", "pleased_to_meet_you"],
        "hi": ["hello", "nice_to_meet_okabe"],
        "你好": ["hello", "nice_to_meet_okabe", "pleased_to_meet_you"],
        "您好": ["hello", "pleased_to_meet_you"],
        "在吗": ["what_is_it", "hello"],
        
        # Christina相关
        "christina": ["christina", "dont_call_me_like_that", "dont_add_tina", "who_the_hell_christina", "why_christina"],
        "克里斯蒂娜": ["christina", "dont_call_me_like_that", "dont_add_tina", "who_the_hell_christina", "why_christina"],
        
        # 帮助
        "help": ["could_i_help", "what_do_you_want", "ask_me_whatever"],
        "帮助": ["could_i_help", "ask_me_whatever"],
        "帮我": ["could_i_help", "what_do_you_want"],
        "做什么": ["what_do_you_want", "ask_me_whatever"],
        "能做什么": ["could_i_help", "ask_me_whatever"],
        
        # 道歉
        "sorry": ["sorry", "i_guess", "i_see"],
        "对不起": ["sorry", "i_guess"],
        "抱歉": ["sorry", "i_see"],
        "不好意思": ["sorry"],
        
        # 确认
        "ok": ["ok", "nice", "heheh"],
        "好的": ["ok", "nice"],
        "知道了": ["ok", "i_see"],
        "明白": ["ok", "i_see"],
        "是": ["ok", "nice"],
        "对": ["ok", "nice"],
        
        # 时间
        "time": ["tm_you_said", "tm_too_early", "tm_nonsense"],
        "时间": ["tm_you_said", "tm_too_early"],
        "几点": ["tm_you_said"],
        "什么时候": ["tm_you_said", "tm_too_early"],
        
        # 记忆
        "memory": ["memory_complex", "modifying_memories_impossible", "memories_christina"],
        "记忆": ["memory_complex", "modifying_memories_impossible", "memories_christina"],
        "忘记": ["memory_complex", "modifying_memories_impossible"],
        "记得": ["memory_complex", "memories_christina"],
        
        # 变态相关
        "pervert": ["pervert_confirmed", "perverts_go_to_hell", "pervert_idot_wanttodie", "devilish_pervert"],
        "变态": ["pervert_confirmed", "perverts_go_to_hell", "pervert_idot_wanttodie"],
        "色狼": ["pervert_confirmed", "devilish_pervert"],
        "讨厌": ["pervert_confirmed", "gah"],
        
        # 前辈
        "senpai": ["senpai_question", "senpai_please_dont_tell", "uh_senpai", "senpai_who_is_this"],
        "前辈": ["senpai_question", "uh_senpai", "senpai_who_is_this"],
        "学长": ["senpai_question", "senpai_please_dont_tell"],
        "学姐": ["senpai_question"],
        
        # 情绪表达
        "开心": ["happy", "heheh", "nice"],
        "高兴": ["happy", "heheh"],
        "难过": ["sorry", "sounds_tough"],
        "伤心": ["sorry", "sad"],
        "生气": ["angry", "gah"],
        "愤怒": ["angry", "pissed"],
        
        # 疑问
        "为什么": ["huh_why_say", "you_sure"],
        "怎么": ["huh_why_say", "what_is_it"],
        "什么": ["what_is_it", "what_do_you_want"],
        "谁": ["who_the_hell_christina", "senpai_who_is_this"],
        
        # 感谢
        "谢谢": ["nice", "ok", "heheh"],
        "感谢": ["nice", "pleased_to_meet_you"],
        
        # 告别
        "再见": ["nice_to_meet_okabe", "look_forward_to_working"],
        "拜拜": ["nice_to_meet_okabe"],
        "晚安": ["nice_to_meet_okabe", "look_forward_to_working"],
        
        # 默认响应
        "default": ["what_is_it", "huh_why_say", "you_sure", "sounds_tough", "humans_software"]
    }
    
    # 最近使用的预设回答记录，用于避免连续重复（key=关键词, value=最近使用的音频列表）
    _recent_responses = {}
    _MAX_RECENT = 3  # 每个关键词最多记住 3 条最近使用记录
    
    @classmethod
    def get_response(cls, text: str) -> str:
        """根据输入文本匹配一个预设语音文件名（优先避免最近使用过的）"""
        text_lower = text.lower()
        
        for keyword, responses in cls.RESPONSES.items():
            if keyword in text_lower:
                # 获取最近使用的响应列表
                recent = cls._recent_responses.get(keyword, [])
                # 过滤掉最近使用的响应
                available_responses = [r for r in responses if r not in recent]
                # 如果没有可用响应，使用所有响应
                if not available_responses:
                    available_responses = responses
                # 随机选择一个响应
                selected = random.choice(available_responses)
                # 更新最近使用的响应
                recent.append(selected)
                if len(recent) > cls._MAX_RECENT:
                    recent.pop(0)
                cls._recent_responses[keyword] = recent
                return selected
        
        # 处理默认响应
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
        """随机返回一个问候语预设音频文件名"""
        greetings = ["hello", "nice_to_meet_okabe", "pleased_to_meet_you"]
        return random.choice(greetings)
    
    @classmethod
    def get_all_matching_responses(cls, text: str) -> list:
        """返回所有与输入文本匹配的预设音频文件名列表（合并多个关键词的匹配结果）"""
        text_lower = text.lower()
        matching = []
        
        for keyword, responses in cls.RESPONSES.items():
            if keyword in text_lower and keyword != "default":
                # 获取最近使用的响应列表
                recent = cls._recent_responses.get(keyword, [])
                # 过滤掉最近使用的响应
                available_responses = [r for r in responses if r not in recent]
                # 如果没有可用响应，使用所有响应
                if not available_responses:
                    available_responses = responses
                matching.extend(available_responses)
        
        if not matching:
            # 处理默认响应
            recent = cls._recent_responses.get("default", [])
            available_responses = [r for r in cls.RESPONSES["default"] if r not in recent]
            if not available_responses:
                available_responses = cls.RESPONSES["default"]
            matching.extend(available_responses)
        
        return matching
    
    # 预设语音的中文文本内容映射（用于 AI 选择预设时提供语义描述，以及聊天框打字机显示）
    PRESET_TEXT_MAP = {
        # 问候语
        "hello": "你好。",
        "nice_to_meet_okabe": "很高兴见到你，冈部。",
        "pleased_to_meet_you": "很高兴认识你。",
        "look_forward_to_working": "期待与你合作。",
        
        # Christina相关
        "christina": "我说了不要叫我克里斯蒂娜！",
        "dont_call_me_like_that": "不要那样叫我！",
        "dont_add_tina": "不要加蒂娜！",
        "who_the_hell_christina": "谁是克里斯蒂娜啊！",
        "why_christina": "为什么是克里斯蒂娜？",
        
        # 帮助/询问
        "could_i_help": "有什么我可以帮忙的吗？",
        "what_do_you_want": "你想要什么？",
        "ask_me_whatever": "尽管问吧。",
        "what_is_it": "什么事？",
        
        # 道歉/确认
        "sorry": "对不起。",
        "i_guess": "我想是吧。",
        "i_see": "我明白了。",
        "ok": "好的。",
        "nice": "不错。",
        "heheh": "呵呵。",
        "you_sure": "你确定吗？",
        
        # 疑问
        "huh_why_say": "嗯？为什么这么说？",
        "sounds_tough": "听起来很困难。",
        "humans_software": "人类就像软件一样。",
        
        # 记忆相关
        "memory_complex": "记忆是很复杂的。",
        "modifying_memories_impossible": "修改记忆是不可能的。",
        
        # 变态相关
        "pervert_confirmed": "确认是变态。",
        "perverts_go_to_hell": "变态去死吧！",
        "pervert_idot_wanttodie": "你这个变态白痴，想死吗？",
        "devilish_pervert": "恶魔般的变态。",
        
        # 前辈相关
        "senpai_question": "前辈？",
        "senpai_please_dont_tell": "前辈，请不要告诉别人...",
        "uh_senpai": "呃，前辈...",
        
        # 情绪表达
        "happy": "开心~",
        "sad": "难过...",
        "angry": "生气！",
        "pissed": "愤怒！",
        "gah": "啊！",
        "blush": "（脸红）",
        
        # 时间相关
        "tm_you_said": "时间机器的话...你是说...",
        "tm_too_early": "时间机器那种东西还太早了。",
        "tm_nonsense": "胡说八道。",
    }

    # 预设语音的日文台词，用于角色左下角字幕显示。
    PRESET_JAPANESE_TEXT_MAP = {
        "hello": "こんにちは。",
        "nice_to_meet_okabe": "初めまして、岡部。",
        "pleased_to_meet_you": "よろしく。",
        "look_forward_to_working": "これからよろしく。",
        "christina": "クリスティーナって呼ぶな！",
        "dont_call_me_like_that": "そう呼ばないで！",
        "dont_add_tina": "ティーナを付けるな！",
        "who_the_hell_christina": "誰がクリスティーナよ！",
        "why_christina": "なんでクリスティーナなのよ！",
        "memories_christina": "クリスティーナの記憶？",
        "should_christina": "クリスティーナって呼ぶべきなの？",
        "could_i_help": "何か手伝えることある？",
        "what_do_you_want": "何が望みなの？",
        "ask_me_whatever": "何でも聞いて。",
        "what_is_it": "何？",
        "sorry": "ごめんなさい。",
        "i_guess": "たぶんね。",
        "i_see": "なるほど。",
        "ok": "わかった。",
        "nice": "悪くないわね。",
        "heheh": "ふふっ。",
        "you_sure": "本気で言ってるの？",
        "still_not_happy": "まだ納得してないわ。",
        "huh_why_say": "は？なんでそうなるの？",
        "sounds_tough": "それは大変そうね。",
        "humans_software": "人間はソフトウェアみたいなものよ。",
        "memory_complex": "記憶って複雑なのよ。",
        "modifying_memories_impossible": "記憶を書き換えるなんて不可能よ。",
        "secret_diary": "秘密の日記？",
        "pervert_confirmed": "変態確定ね。",
        "perverts_go_to_hell": "変態は地獄に落ちなさい！",
        "pervert_idot_wanttodie": "この変態バカ、死にたいの？",
        "devilish_pervert": "悪魔的な変態ね。",
        "this_guy_hopeless": "こいつ、もう駄目ね。",
        "senpai_question": "先輩？",
        "senpai_please_dont_tell": "先輩、誰にも言わないでください……",
        "uh_senpai": "あ、先輩……",
        "senpai_who_is_this": "先輩、これは誰ですか？",
        "senpai_what_we_talkin": "先輩、何の話をしてるんですか？",
        "senpai_questionmark": "先輩……？",
        "whats_so_funny_senpai": "先輩、何がおかしいんですか？",
        "gah": "ああっ！",
        "gah_extended": "ああああっ！",
        "daga_kotowaru": "だが断る！",
        "happy": "嬉しい。",
        "sad": "悲しい……",
        "angry": "怒ってるの！",
        "pissed": "腹立つ！",
        "tm_you_said": "タイムマシンって言った？",
        "tm_too_early": "まだ早すぎるわ。",
        "tm_nonsense": "馬鹿なこと言わないで。",
        "tm_not_possible": "ありえない。",
        "tm_scientist_no_evidence": "科学者に証拠は必要よ。",
        "tm_we_dont_know": "私たちにはまだ分からない。",
        "leskinen_awesome": "素晴らしいですね。",
        "leskinen_holy_cow": "なんということでしょう。",
        "leskinen_nice": "いいですね。",
        "leskinen_oh_no": "おお、いけません。",
        "leskinen_shaman": "シャーマンですね。",
    }
    
    # 音频文件名 → 角色表情名的映射（播放预设音频时同步切换角色表情）
    AUDIO_EMOTION_MAP = {
        # 开心/友好
        "hello": "happy",
        "nice_to_meet_okabe": "happy",
        "pleased_to_meet_you": "happy",
        "look_forward_to_working": "happy",
        "heheh": "happy",
        "nice": "happy",
        "happy": "happy",
        "ok": "happy",
        "ask_me_whatever": "happy",

        # 生气/愤怒
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
        
        # 害羞
        "blush": "blush",
        "sided_blush": "blush",
        "dont_look_at_me": "blush",
        
        # 烦恼/困扰
        "annoyed": "annoyed",
        "what_do_you_want": "annoyed",
        "sounds_tough": "annoyed",
        "devilish_pervert": "annoyed",
        
        # 失望
        "disappointed": "disappointed",
        "sorry": "disappointed",
        "sad": "sad",
        
        # 闭眼/思考
        "eyes_closed": "eyes_closed",
        "sided_eyes_closed": "eyes_closed",
        "i_see": "eyes_closed",
        "i_guess": "eyes_closed",
        
        # 冷淡/无所谓
        "indifferent": "indifferent",
        "tm_nonsense": "indifferent",
        "tm_not_possible": "indifferent",
        "humans_software": "indifferent",
        
        # 侧脸/思考
        "side": "side",
        "sided_thinking": "side",
        "sided_worried": "side",
        "memory_complex": "side",
        "modifying_memories_impossible": "side",
        
        # 惊讶
        "sided_surprised": "sided_surprised",
        "huh_why_say": "sided_surprised",

        # 愉快
        "sided_pleasant": "sided_pleasant",
        "could_i_help": "sided_pleasant",
        
        # 眨眼
        "winking": "winking",
        "you_sure": "winking",
        
        # 默认
        "default": "normal"
    }
    
    @classmethod
    def get_emotion_for_audio(cls, audio_name: str) -> str:
        """根据音频文件名获取对应的角色表情名，未匹配到则返回 'normal'"""
        return cls.AUDIO_EMOTION_MAP.get(audio_name, "normal")

    @classmethod
    def get_japanese_text_for_audio(cls, audio_name: str) -> str:
        """根据预设音频文件名获取角色字幕用的日文台词。"""
        return cls.PRESET_JAPANESE_TEXT_MAP.get(audio_name, "")
