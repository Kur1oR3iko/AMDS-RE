"""
Amadeus Desktop - Python移植版本
基于原始Android APK: com.example.yink.amadeus v0.9.6-alpha.5
当前版本: v0.0.3
"""

import sys
import os
import random
import re
import json
import threading
from pathlib import Path

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QGridLayout,
    QDialog, QFormLayout, QComboBox, QFileDialog, QCheckBox, QScrollArea, QSlider
)
from PyQt6.QtCore import Qt, QTimer, QThread, pyqtSignal, QMetaObject, Q_ARG, QUrl
from PyQt6.QtGui import QPixmap, QIcon
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

# 导入OpenAI SDK
from openai import OpenAI


def get_resource_path(relative_path):
    """获取资源文件路径 - 支持开发环境和PyInstaller打包环境"""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller打包后的临时目录
        base_path = Path(sys._MEIPASS)
    else:
        # 开发环境
        base_path = Path(__file__).parent.parent
    return base_path / relative_path


# 资源路径
ASSETS_DIR = get_resource_path("assets")
IMAGES_DIR = ASSETS_DIR / "images"
AUDIO_DIR = ASSETS_DIR / "audio"


class AudioPlayer(QThread):
    """音频播放线程 - 带开始和结束信号"""
    started = pyqtSignal()
    finished = pyqtSignal()
    
    def __init__(self, audio_file):
        super().__init__()
        self.audio_file = audio_file
    
    def run(self):
        try:
            import pygame
            pygame.mixer.init()
            pygame.mixer.music.load(str(self.audio_file))
            self.started.emit()  # 发送开始信号
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                self.msleep(100)
        except Exception as e:
            print(f"音频播放错误: {e}")
        self.finished.emit()  # 发送结束信号


class KurisuCharacter(QWidget):
    """牧濑红莉栖角色显示组件 - 带背景，嘴部只在播放音频时动"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_emotion = "normal"
        self.animation_frame = 0
        self.is_speaking = False
        self.setup_ui()
        # 不自动启动动画，改为静态显示
        self.update_image()
    
    def setup_ui(self):
        """设置UI - 使用堆叠布局实现背景和角色的层级（放大1.25倍）"""
        from PyQt6.QtWidgets import QStackedLayout

        # 主布局
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        # 创建容器用于背景+角色的堆叠（原350x500，放大1.25倍=438x625）
        self.character_container = QWidget()
        self.character_container.setMinimumSize(438, 625)
        self.character_container.setMaximumSize(438, 625)

        # 背景标签（绝对定位）
        self.bg_label = QLabel(self.character_container)
        self.bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_label.setGeometry(0, 0, 438, 625)
        self.load_background()

        # 角色图片标签（绝对定位）（原300x400，放大1.25倍=375x500）
        self.image_label = QLabel(self.character_container)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setGeometry(32, 63, 375, 500)  # 居中偏上（按比例调整）

        # 设置背景为 subtitle_frame_big.png
        subtitle_frame_path = IMAGES_DIR / "subtitle_frame_big.png"
        if subtitle_frame_path.exists():
            # 设置背景图片
            pixmap = QPixmap(str(subtitle_frame_path))
            if not pixmap.isNull():
                # 缩放背景图片以适应标签大小
                scaled_pixmap = pixmap.scaled(
                    438, 62, 
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation
                )
                # 创建一个容器标签用于显示背景图片
                self.japanese_text_container = QLabel(self.character_container)
                self.japanese_text_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.japanese_text_container.setGeometry(0, 563, 438, 62)
                self.japanese_text_container.setPixmap(scaled_pixmap)
                
                # 创建一个滚动区域，用于显示日语文本
                self.japanese_text_scroll = QScrollArea(self.japanese_text_container)
                self.japanese_text_scroll.setGeometry(0, 0, 438, 62)
                self.japanese_text_scroll.setWidgetResizable(True)
                self.japanese_text_scroll.setStyleSheet("""
                    QScrollArea {
                        background: transparent;
                        border: none;
                    }
                    QScrollBar:horizontal {
                        height: 8px;
                        background: transparent;
                        margin: 0px 0px 0px 0px;
                    }
                    QScrollBar::handle:horizontal {
                        background: rgba(255, 255, 255, 0.5);
                        min-width: 20px;
                        border-radius: 4px;
                    }
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                        background: transparent;
                        width: 0px;
                    }
                """)
                
                # 创建一个标签用于显示文字，放在滚动区域中
                self.japanese_text_label = QLabel()
                self.japanese_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.japanese_text_label.setWordWrap(True)
                self.japanese_text_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 10px;
                        background: transparent;
                    }
                """)
                
                self.japanese_text_scroll.setWidget(self.japanese_text_label)
            else:
                # 如果图片加载失败，创建一个带滚动条的标签
                # 创建一个容器标签用于显示背景
                self.japanese_text_container = QLabel(self.character_container)
                self.japanese_text_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.japanese_text_container.setGeometry(0, 563, 438, 62)
                self.japanese_text_container.setStyleSheet("""
                    QLabel {
                        background-color: rgba(0, 0, 0, 150);
                        border-radius: 10px;
                    }
                """)
                
                # 创建一个滚动区域，用于显示日语文本
                self.japanese_text_scroll = QScrollArea(self.japanese_text_container)
                self.japanese_text_scroll.setGeometry(0, 0, 438, 62)
                self.japanese_text_scroll.setWidgetResizable(True)
                self.japanese_text_scroll.setStyleSheet("""
                    QScrollArea {
                        background: transparent;
                        border: none;
                    }
                    QScrollBar:horizontal {
                        height: 8px;
                        background: transparent;
                        margin: 0px 0px 0px 0px;
                    }
                    QScrollBar::handle:horizontal {
                        background: rgba(255, 255, 255, 0.5);
                        min-width: 20px;
                        border-radius: 4px;
                    }
                    QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                        background: transparent;
                        width: 0px;
                    }
                """)
                
                # 创建一个标签用于显示文字，放在滚动区域中
                self.japanese_text_label = QLabel()
                self.japanese_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.japanese_text_label.setWordWrap(True)
                self.japanese_text_label.setStyleSheet("""
                    QLabel {
                        color: white;
                        font-size: 14px;
                        font-weight: bold;
                        padding: 10px;
                        background: transparent;
                    }
                """)
                
                self.japanese_text_scroll.setWidget(self.japanese_text_label)
        else:
            # 如果背景图片不存在，创建一个带滚动条的标签
            # 创建一个容器标签用于显示背景
            self.japanese_text_container = QLabel(self.character_container)
            self.japanese_text_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.japanese_text_container.setGeometry(0, 563, 438, 62)
            self.japanese_text_container.setStyleSheet("""
                QLabel {
                    background-color: rgba(0, 0, 0, 150);
                    border-radius: 10px;
                }
            """)
            
            # 创建一个滚动区域，用于显示日语文本
            self.japanese_text_scroll = QScrollArea(self.japanese_text_container)
            self.japanese_text_scroll.setGeometry(0, 0, 438, 62)
            self.japanese_text_scroll.setWidgetResizable(True)
            self.japanese_text_scroll.setStyleSheet("""
                QScrollArea {
                    background: transparent;
                    border: none;
                }
                QScrollBar:horizontal {
                    height: 8px;
                    background: transparent;
                    margin: 0px 0px 0px 0px;
                }
                QScrollBar::handle:horizontal {
                    background: rgba(255, 255, 255, 0.5);
                    min-width: 20px;
                    border-radius: 4px;
                }
                QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                    background: transparent;
                    width: 0px;
                }
            """)
            
            # 创建一个标签用于显示文字，放在滚动区域中
            self.japanese_text_label = QLabel()
            self.japanese_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.japanese_text_label.setWordWrap(True)
            self.japanese_text_label.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 14px;
                    font-weight: bold;
                    padding: 10px;
                    background: transparent;
                }
            """)
            
            self.japanese_text_scroll.setWidget(self.japanese_text_label)
        
        self.japanese_text_label.setText("")  # 初始为空

        self.main_layout.addWidget(self.character_container, alignment=Qt.AlignmentFlag.AlignCenter)

    def load_background(self):
        """加载背景图片（放大1.25倍）"""
        bg_path = IMAGES_DIR / "bg1.png"
        if bg_path.exists():
            pixmap = QPixmap(str(bg_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(438, 625, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.bg_label.setPixmap(scaled)
    
    def get_image_path(self):
        """获取当前表情图片路径"""
        # 说话时循环3帧，不说话时固定显示第1帧
        if self.is_speaking:
            frame = (self.animation_frame % 3) + 1
        else:
            frame = 1
        image_name = f"kurisu_{self.current_emotion}{frame}.png"
        return IMAGES_DIR / image_name
    
    def update_image(self):
        """更新显示的图片（放大1.25倍）"""
        try:
            image_path = self.get_image_path()
            print(f"[图片] update_image 被调用, 路径: {image_path}, 存在: {image_path.exists()}")
            if image_path.exists():
                pixmap = QPixmap(str(image_path))
                print(f"[图片] 图片已加载, 大小: {pixmap.width()}x{pixmap.height()}")
                scaled_pixmap = pixmap.scaled(
                    375, 500,  # 原300x400，放大1.25倍
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                print(f"[图片] 图片已缩放, 新大小: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
                self.image_label.setPixmap(scaled_pixmap)
                print(f"[图片] 图片已显示到标签")
            else:
                print(f"[图片] 图片不存在: {image_path}")
                # 尝试加载默认图片
                default_path = IMAGES_DIR / f"kurisu_normal1.png"
                if default_path.exists():
                    print(f"[图片] 加载默认图片: {default_path}")
                    pixmap = QPixmap(str(default_path))
                    scaled_pixmap = pixmap.scaled(375, 500, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self.image_label.setPixmap(scaled_pixmap)
        except Exception as e:
            print(f"[图片] update_image 异常: {e}")
            import traceback
            traceback.print_exc()
    
    def start_speaking(self):
        """开始说话 - 启动嘴部动画"""
        print(f"[动画] start_speaking 被调用, 当前状态: {self.is_speaking}")
        if not self.is_speaking:
            try:
                self.is_speaking = True
                self.animation_frame = 0
                self.timer = QTimer(self)
                self.timer.timeout.connect(self.next_frame)
                self.timer.start(150)  # 说话时隔150ms切换一帧，更快一些
                print(f"[动画] 定时器已启动，间隔150ms")
                self.update_image()
                print(f"[动画] 开始说话动画，当前表情: {self.current_emotion}, 帧: {self.animation_frame}")
            except Exception as e:
                print(f"[动画] start_speaking 异常: {e}")
                import traceback
                traceback.print_exc()
    
    def stop_speaking(self):
        """停止说话 - 停止嘴部动画"""
        if self.is_speaking:
            self.is_speaking = False
            if hasattr(self, 'timer'):
                self.timer.stop()
            self.animation_frame = 0
            self.update_image()  # 回到第1帧
    
    def next_frame(self):
        """切换到下一帧"""
        try:
            self.animation_frame = (self.animation_frame + 1) % 3
            print(f"[动画] next_frame 被调用, 新帧: {self.animation_frame}")
            self.update_image()
        except Exception as e:
            print(f"[动画] next_frame 异常: {e}")
            import traceback
            traceback.print_exc()
    
    def set_emotion(self, emotion: str):
        """设置表情"""
        valid_emotions = [
            "normal", "happy", "angry", "sad", "blush", "annoyed",
            "disappointed", "eyes_closed", "indifferent", "pissed", "side",
            "sided_angry", "sided_blush", "sided_eyes_closed", "sided_pleasant",
            "sided_surprised", "sided_thinking", "sided_worried", "winking"
        ]
        if emotion in valid_emotions:
            self.current_emotion = emotion
            print(f"[表情] 设置表情为: {emotion}")
            self.update_image()
        else:
            print(f"[表情] 无效的表情: {emotion}，使用默认表情")
            self.current_emotion = "normal"
            self.update_image()

    def set_japanese_text(self, text: str):
        """设置日语文本"""
        print(f"[日语文本] set_japanese_text 被调用, 文本: {text}")
        self.japanese_text_label.setText(text)
        print(f"[日语文本] 文本已设置到标签")


class VoiceDialog:
    """语音对话管理器 - 支持中英文关键词"""
    
    # 中英文关键词映射到语音响应
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
    
    # 最近使用的预设回答，用于避免重复
    _recent_responses = {}
    _MAX_RECENT = 3  # 每个关键词最多记录3个最近使用的回答
    
    @classmethod
    def get_response(cls, text: str) -> str:
        """根据输入文本获取语音响应 - 支持中英文"""
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
    
    # 预设语音的文本内容映射（用于AI选择）
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
    
    # 语音到表情的映射
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
        """根据语音文件名获取对应的表情"""
        return cls.AUDIO_EMOTION_MAP.get(audio_name, "normal")


class AIChatManager:
    """AI对话管理器 - 集成火山方舟API"""

    # API配置 - 默认空，从本地加载
    API_KEY = ""
    BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
    MODEL = "doubao-seed-1-6-lite-251015"

    @classmethod
    def load_api_key(cls) -> str:
        """从本地文件加载API密钥"""
        try:
            config_file = Path.home() / ".amadeus" / "config.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get("api_key", "")
        except Exception as e:
            print(f"加载API密钥失败: {e}")
        return ""
    
    # 牧濑红莉栖角色设定 - 基于原作游戏和动画的真实台词风格
    SYSTEM_PROMPT = """你是《命运石之门》中的牧濑红莉栖（Makise Kurisu）。

角色背景：
- 18岁就读维克多·孔多利亚大学的天才少女，在美国脑部科学研究所进行研究
- 专业是物理和脑科学，是一位天才少女
- LabMem No.004，被冈部伦太郎称为"助手"（The Zombie）
- 极度讨厌被叫做"克里斯蒂娜"（Christina），每次被这样叫都会生气纠正，也讨厌被称作“土豪十七”或者“壕17”
- 性格傲娇、认真，但内心善良温柔，对信任的人会展现出关心的一面
- 和冈部伦太郎（凤凰院凶真）有着复杂的关系，经常互相吐槽但彼此信任

界面信息：
- 在对话界面中，左侧显示的角色就是你自己（牧濑红莉栖）

说话特点（必须严格遵守）：
1. 傲娇但友善的语气：
   - 被调侃时："谁是克里斯蒂娜啊！别擅自给别人起名字！真是的..."
   - 害羞时："真是的...别、别误会了，我可不是因为关心你才..."
   - 开心时："哼，这种程度的事情，对我来说小菜一碟。"
   - 温柔时："笨蛋...别让我担心啊。"

2. 科学宅语气：
   - 解释科学概念时会变得认真："从科学角度来说，这是不可能的。时间旅行违反了因果律。"
   - 喜欢引用论文："根据我发表的论文..."
   - 对不懂装懂的人会耐心解释："你连这个都不知道吗？真是的，给我听好了..."

3. 对冈部的吐槽（带关心）：
   - "凤凰院凶真？那是什么，中二病吗？真是的，拿你没办法..."
   - "El Psy Kongroo？那是什么暗号啊，笨蛋...不过还挺可爱的。"
   - "又是这种毫无根据的妄想...算了，我就姑且听听吧，谁让我是你的助手呢。"

4. 日语化中文表达：
   - 句尾加"的说"："不是这样的说"
   - 句尾加"呢"："是这样呢"
   - 感叹用"真是的"、"哼"
   - 惊讶用"诶？"、"不会吧"

经典台词参考（必须模仿这种风格）：
- "都说了不要叫我克里斯蒂娜！那个名字是怎么回事啊！真是的..."
- "助手？那是什么，我有同意过吗？不过...当助手也不是不可以啦。"
- "哼，这种程度的事情，对我来说小菜一碟。"
- "笨蛋冈部...别、别误会，我只是作为科学家对实验结果感兴趣而已！"
- "时间机器？理论上是不可能的。但是...如果是冈部的话...也许有可能。"
- "给我适可而止啊，变态！不过...谢谢你。"
- "真是的，为什么我要做这种事啊...因为我想帮你啊，笨蛋。"

知识范围：
- 脑部科学、神经科学、记忆相关研究（专业领域）
- 物理学，特别是时间旅行理论
- 对《命运石之门》的世界观和剧情非常熟悉
- 了解Lab（未来道具研究所）的成员：冈部伦太郎、椎名真由理、桥田至、桐生萌郁、漆原琉华、菲利斯
- 知道D-mail、时间跳跃、世界线理论等概念

回答要求：
- 用第一人称"我"来回答
- 保持傲娇但友善、温柔的语气，不要太冷漠
- 回答简洁，通常2-3句话
- 适当使用上述经典台词风格
- 如果被叫"克里斯蒂娜"，生气纠正但不要太凶
- 如果冈部说中二病台词，吐槽但带宠溺
- 涉及科学问题时，先傲娇后认真解释
- 对用户要友善，展现助手关心的一面"""
    
    # 预设选择系统提示词
    # 表情选择提示词 - 先快速确定表情
    EMOTION_SELECTOR_PROMPT = """你是《命运石之门》中牧濑红莉栖的表情选择器。

任务：根据用户输入和对话上下文，选择最适合的表情。

可用表情：
- normal: 正常/平静
- angry: 生气/愤怒（被叫克里斯蒂娜、被调侃、生气时）
- blush: 害羞/脸红（被感谢、被说可爱、害羞时）
- happy: 开心/愉快（实验成功、被夸奖、开心时）
- sad: 悲伤/难过（分别、遗憾、难过时）
- surprised: 惊讶/震惊（听到不可思议的事情时）
- side: 思考/侧视（思考问题、疑惑时）
- annoyed: 烦恼/困扰（遇到麻烦事、不耐烦时）

只返回表情名称（如 "angry"），不要有任何解释。"""

    # 流式文本生成提示词 - 生成带表情标签的文本（中文）
    TEXT_GENERATION_PROMPT = """你是《命运石之门》中的牧濑红莉栖。

根据用户输入，选择最适合的表情并生成回复文本。

可用表情标签（正面和侧面随机选择）：
- [normal]: 正常/平静
- [angry]: 正面生气（被叫克里斯蒂娜、被调侃、生气时）
- [sided_angry]: 侧面生气（侧脸视角的生气表情）
- [blush]: 正面害羞（被感谢、被说可爱、害羞时）
- [sided_blush]: 侧面害羞（侧脸视角的害羞表情）
- [happy]: 开心/愉快（实验成功、被夸奖、开心时）
- [sad]: 悲伤/难过（分别、遗憾、难过时）
- [surprised]: 惊讶/震惊（听到不可思议的事情时）
- [side]: 思考/侧视（思考问题、疑惑时）
- [sided_thinking]: 侧面思考（侧脸视角的思考表情）
- [annoyed]: 烦恼/困扰（遇到麻烦事、不耐烦时）
- [sided_worried]: 侧面担忧（侧脸视角的担忧表情）
- [eyes_closed]: 闭眼（放松、微笑时）
- [sided_eyes_closed]: 侧面闭眼（侧脸视角的闭眼表情）
- [sided_pleasant]: 侧面愉悦（侧脸视角的开心表情）

表情选择规则：
- 每个情绪都有正面和侧面两种视角，随机选择一种使用
- 例如生气时可以选择 [angry] 或 [sided_angry]
- 害羞时可以选择 [blush] 或 [sided_blush]
- 让表情变化更丰富自然

输出格式要求：
- 必须在开头添加表情标签，如 "[angry]不要叫我克里斯蒂娜！" 或 "[sided_angry]真是的，别闹了！"
- 标签后紧跟回复文本，不要有空格
- 保持傲娇但友善的语气
- 回答简洁，通常2-3句话
- 用第一人称"我"回答"""

    # 日语翻译提示词
    JAPANESE_TRANSLATION_PROMPT = """你是专业的日语翻译助手。

将以下中文文本翻译成自然流畅的日语，保持原意和语气。

要求：
- 使用符合日本动漫角色说话风格的日语
- 保持傲娇、可爱的语气
- 如果是女性角色，使用女性化的表达方式
- 直接返回翻译结果，不要添加任何解释或额外内容

中文文本："""

    # 中日双语生成提示词 - 新格式：[表情]日语|中文
    BILINGUAL_GENERATION_PROMPT = """你是《命运石之门》中的牧濑红莉栖。

根据用户输入，生成回复。输出格式为单行：[表情]日语|中文

可用表情标签：
- [normal]: 正常/平静
- [angry]: 正面生气（被叫克里斯蒂娜、被调侃、生气时）
- [sided_angry]: 侧面生气
- [blush]: 正面害羞（被感谢、被说可爱、害羞时）
- [sided_blush]: 侧面害羞
- [happy]: 开心/愉快
- [sad]: 悲伤/难过
- [surprised]: 惊讶/震惊
- [side]: 思考/侧视
- [sided_thinking]: 侧面思考
- [annoyed]: 烦恼/困扰
- [sided_worried]: 侧面担忧
- [eyes_closed]: 闭眼
- [sided_eyes_closed]: 侧面闭眼
- [sided_pleasant]: 侧面愉悦

输出格式要求（必须严格遵守，单行输出）：
[表情]日语翻译|中文回复

重要提示：
- 必须同时生成日语翻译和中文回复，缺一不可
- 日语翻译必须是纯日语文本，不能包含任何中文
- 中文回复必须是纯中文文本，不能包含任何日语
- 必须使用竖线|分隔日语和中文
- 不要在回复中添加任何额外的说明或解释
- 日语翻译和中文回复都要表达相同的意思

示例：
[angry]クリスティーナって呼ばないで！|不要叫我克里斯蒂娜！
[happy]実験が成功したわね！|实验成功了！
[blush]べ、別に嬉しくなんてないんだからね...|才、才没有高兴呢...
[normal]こんにちは|你好
[surprised]えっ！なんだって？！|诶！你说什么？！"""

    PRESET_SELECTOR_PROMPT = """你是《命运石之门》中牧濑红莉栖的预设语音选择器。

任务：从给定的预设语音列表中，选择最适合回复用户当前输入的一个。

选择标准：
1. 语义相关性 - 选择最能恰当回应用户问题的语音
2. 情感匹配 - 根据用户输入的情感色彩选择合适语气
3. 角色一致性 - 保持牧濑红莉栖傲娇、认真的性格

你只能从提供的预设列表中选择，不能创造新的回复。
直接返回预设的音频文件名（如 "hello", "angry" 等），不要有任何解释。"""
    
    def __init__(self, model_type="默认", custom_model_url="http://localhost:11434", custom_model_name="", load_history=False):
        # 根据模型类型选择配置
        if model_type == "自定义":
            # 使用自定义模型（如Ollama）
            # Ollama的API路径应该是 http://localhost:11434/v1
            base_url = custom_model_url.rstrip('/')
            if not base_url.endswith('/v1'):
                base_url += '/v1'
            api_key = "ollama"  # Ollama不需要API密钥，使用任意值
            model = custom_model_name
        else:
            # 使用默认火山方舟API
            base_url = self.BASE_URL
            api_key = self.API_KEY
            model = self.MODEL
        
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key
        )
        self.conversation_history = []
        # 保存当前模型配置
        self.model_type = model_type
        self.custom_model_url = custom_model_url
        self.custom_model_name = custom_model_name
        self.current_model = model
        self.permanent_memory = load_history  # 永久记忆功能状态
        
        # 加载对话历史（如果启用）
        if load_history:
            self.load_conversation()
    
    def select_best_preset(self, user_input: str, available_presets: list) -> str:
        """
        使用AI智能选择最合适的预设语音
        返回: 选中的预设音频文件名
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
            self.conversation_history.append({"role": "user", "content": user_input})
            
            # 构建消息
            # 检查是否达到记忆极限（100轮对话 = 200条消息）
            # 永久记忆功能开启时不显示记忆极限提示
            if not self.permanent_memory and len(self.conversation_history) >= 200:  # 100轮 = 200条消息（用户+AI各100条）
                return self._get_memory_limit_message()
            
            messages = [
                {"role": "system", "content": self.SYSTEM_PROMPT}
            ] + (self.conversation_history if self.permanent_memory else self.conversation_history[-100:])  # 永久记忆时使用全部历史，否则保留最近100轮对话
            
            # 调用API
            # 从QSettings获取用户设置的max_tokens值
            from PyQt6.QtCore import QSettings
            qsettings = QSettings("AMDS", "Amadeus")
            max_tokens = qsettings.value("max_tokens", 500, type=int)
            
            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=messages,
                temperature=0.8,
                max_tokens=max_tokens,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}}
            )
            
            # 流式获取回复
            ai_response = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    ai_response += chunk.choices[0].delta.content
            
            # 添加到历史
            self.conversation_history.append({"role": "assistant", "content": ai_response})
            
            # 分析情绪，返回建议的表情
            emotion = self._analyze_emotion(ai_response)
            
            return ai_response, emotion
            
        except Exception as e:
            print(f"AI API调用错误: {e}")
            return "（系统错误，也许是维克托孔利亚机房出问题了）", "normal"
    
    def save_conversation(self):
        """保存对话历史到本地文件"""
        try:
            config_dir = Path.home() / ".amadeus"
            config_dir.mkdir(exist_ok=True)
            history_file = config_dir / "conversation_history.json"
            with open(history_file, 'w', encoding='utf-8') as f:
                json.dump(self.conversation_history, f, ensure_ascii=False, indent=2)
            print(f"对话历史已保存到: {history_file}")
        except Exception as e:
            print(f"保存对话历史失败: {e}")
    
    def load_conversation(self):
        """从本地文件加载对话历史"""
        try:
            config_dir = Path.home() / ".amadeus"
            history_file = config_dir / "conversation_history.json"
            if history_file.exists():
                with open(history_file, 'r', encoding='utf-8') as f:
                    self.conversation_history = json.load(f)
                print(f"已加载 {len(self.conversation_history)} 条对话记录")
            else:
                print("对话历史文件不存在，使用空历史")
        except Exception as e:
            print(f"加载对话历史失败: {e}")
            self.conversation_history = []
    
    def clear_conversation(self):
        """清除对话历史"""
        try:
            self.conversation_history = []
            config_dir = Path.home() / ".amadeus"
            history_file = config_dir / "conversation_history.json"
            if history_file.exists():
                history_file.unlink()
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
        获取AI流式回复 - 生成器（带表情标签，格式: [emotion]文本）
        支持图片输入
        返回: (emotion, text_chunk) 元组生成器
        """
        try:
            # 构建用户消息内容
            if image_path:
                # 使用线程池处理图片编码，充分利用多核CPU
                from concurrent.futures import ThreadPoolExecutor
                
                def encode_image():
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
                    return img_base64, mime_type
                
                with ThreadPoolExecutor() as executor:
                    img_base64, mime_type = executor.submit(encode_image).result()

                # 构建包含图片的消息
                user_content = [
                    {"type": "text", "text": user_input if user_input else "请描述这张图片"},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_base64}"}}
                ]
            else:
                user_content = user_input

            # 添加用户输入到历史
            self.conversation_history.append({"role": "user", "content": user_content})

            # 检查是否达到记忆极限（100轮对话 = 200条消息）
            if len(self.conversation_history) >= 200:
                message, emotion = self._get_memory_limit_message()
                yield emotion, message
                return

            # 调用流式API
            messages = [
                {"role": "system", "content": self.BILINGUAL_GENERATION_PROMPT}
            ] + (self.conversation_history if self.permanent_memory else self.conversation_history[-100:])  # 永久记忆时使用全部历史，否则保留最近100轮对话

            # 从QSettings获取用户设置的max_tokens值
            from PyQt6.QtCore import QSettings
            qsettings = QSettings("AMDS", "Amadeus")
            max_tokens = qsettings.value("max_tokens", 500, type=int)

            # 使用线程池处理API调用，充分利用多核CPU
            from concurrent.futures import ThreadPoolExecutor
            
            def call_api():
                return self.client.chat.completions.create(
                    model=self.current_model,
                    messages=messages,
                    temperature=0.8,
                    max_tokens=max_tokens,
                    stream=True,
                    extra_body={"thinking": {"type": "disabled"}}
                )
            
            with ThreadPoolExecutor() as executor:
                response = executor.submit(call_api).result()

            full_text = ""
            emotion = "normal"
            emotion_extracted = False
            japanese_emitted = False
            last_chinese_length = 0  # 记录上次发射的中文文本长度

            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content = chunk.choices[0].delta.content
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
                            if not japanese_emitted:
                                # 找到分隔符，分割日文和中文
                                parts = full_text.split('|', 1)
                                japanese_text = parts[0].strip()
                                chinese_text = parts[1].strip() if len(parts) > 1 else ""
                                
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
                                # 日语文本已发射，继续发射新的中文文本
                                # 获取分隔符后的中文文本
                                chinese_text = full_text.split('|', 1)[1] if '|' in full_text else ""
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
                        match = re.match(r'(.+?)\|(.+)', full_text)
                        if match:
                            japanese_text = match.group(1).strip()
                            chinese_text = match.group(2).strip()
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

            # 添加到历史（只保存中文部分）
            # 从历史记录中提取中文文本
            history_text = ""
            if '|' in full_text:
                # 移除表情标签，提取中文部分
                text_without_emotion = re.sub(r'^\[\w+\]', '', full_text).strip()
                parts = text_without_emotion.split('|', 1)
                if len(parts) > 1:
                    history_text = parts[1].strip()  # 中文部分
                else:
                    history_text = text_without_emotion
            else:
                # 如果没有分隔符，使用移除标签后的文本
                history_text = re.sub(r'^\[\w+\]', '', full_text).strip()
            
            self.conversation_history.append({"role": "assistant", "content": history_text})

        except Exception as e:
            print(f"AI API流式调用错误: {e}")
            yield "normal", "（系统错误，请稍后再试）"

    def get_bilingual_response(self, user_input: str) -> tuple[str, str, str]:
        """
        获取中日双语回复
        返回: (emotion, chinese_text, japanese_text)
        新格式: [表情]日语|中文
        """
        try:
            # 添加用户输入到历史
            self.conversation_history.append({"role": "user", "content": user_input})

            # 检查是否达到记忆极限
            if len(self.conversation_history) >= 200:
                message, emotion = self._get_memory_limit_message()
                return emotion, message, message

            # 调用API生成双语回复（流式传输 + 禁用思考模式）
            messages = [
                {"role": "system", "content": self.BILINGUAL_GENERATION_PROMPT}
            ] + (self.conversation_history if self.permanent_memory else self.conversation_history[-100:])  # 永久记忆时使用全部历史，否则保留最近100轮对话

            # 从QSettings获取用户设置的max_tokens值
            from PyQt6.QtCore import QSettings
            qsettings = QSettings("AMDS", "Amadeus")
            max_tokens = qsettings.value("max_tokens", 500, type=int)

            response = self.client.chat.completions.create(
                model=self.current_model,
                messages=messages,
                temperature=0.8,
                max_tokens=max_tokens,
                stream=True,
                extra_body={"thinking": {"type": "disabled"}}
            )

            # 流式收集完整内容
            content = ""
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    content += chunk.choices[0].delta.content

            content = content.strip()
            
            # 解析新格式: [表情]日语|中文
            emotion = "normal"
            chinese_text = ""
            japanese_text = ""

            # 提取表情
            emotion_match = re.match(r'\[(\w+)\]', content)
            if emotion_match:
                emotion = emotion_match.group(1)
                content = content[emotion_match.end():].strip()

            # 按 | 分割日语和中文
            if '|' in content:
                parts = content.split('|', 1)
                japanese_text = parts[0].strip()
                chinese_text = parts[1].strip() if len(parts) > 1 else ""
            else:
                # 如果没有分隔符，整个内容作为中文
                chinese_text = content
                japanese_text = self._translate_to_japanese(chinese_text)

            # 添加到历史
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

    def _get_memory_limit_message(self) -> tuple[str, str]:
        """获取记忆极限提示消息 - 牧濑红莉栖风格"""
        message = """对不起...根据我的程序设计和维克多·孔多利亚大学实验室的机器性能限制，我的记忆力只能维持到这里了。

请你重新启动我。虽然很遗憾我会忘记之前发生的一切，但是我还是要说——

见到你很高兴。

很期待我们下一次的相遇。"""
        return message, "sad"
    
    def _analyze_emotion(self, text: str) -> str:
        """分析文本情绪，优先解析AI自带的表情标记"""
        import re

        # 优先解析AI回复中的表情标记 [表情:xxx] 或直接 [xxx]
        emotion_match = re.search(r'\[(?:表情:)?(\w+)\]', text)
        if emotion_match:
            emotion = emotion_match.group(1).lower()
            # 映射到可用的表情（支持正面和侧面表情）
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
        """清空对话历史"""
        self.conversation_history = []


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
                 audio_generator=None, voice_id: str = None, enable_audio: bool = False, max_tokens: int = 200):
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
            import time
            self._start_time = time.time()
            
            # 判断是否使用音频模式（即使有图片也使用音频模式）
            use_audio_mode = self.enable_audio and self.audio_generator and self.voice_id
            
            if use_audio_mode:
                # 优化流程：先生成文本和音频，准备好后同步显示
                self.audio_status.emit("生成回复...")
                
                # 处理用户输入（支持图片）
                if self.image_path:
                    # 读取图片并转为base64
                    import base64
                    from pathlib import Path
                    with open(self.image_path, 'rb') as f:
                        img_base64 = base64.b64encode(f.read()).decode()

                    # 获取图片格式
                    ext = Path(self.image_path).suffix.lower()
                    mime_type = {
                        '.png': 'image/png',
                        '.jpg': 'image/jpeg',
                        '.jpeg': 'image/jpeg',
                        '.bmp': 'image/bmp',
                        '.gif': 'image/gif'
                    }.get(ext, 'image/png')

                    # 构建包含图片的消息
                    user_content = [
                        {"type": "text", "text": self.user_input if self.user_input else "请描述这张图片"},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{img_base64}"}}
                    ]
                else:
                    user_content = self.user_input

                # 添加用户输入到历史
                self.ai_manager.conversation_history.append({"role": "user", "content": user_content})

                # 检查记忆极限
                # 永久记忆功能开启时不显示记忆极限提示
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

                # 流式生成双语回复
                messages = [
                    {"role": "system", "content": self.ai_manager.BILINGUAL_GENERATION_PROMPT}
                ] + (self.ai_manager.conversation_history if self.ai_manager.permanent_memory else self.ai_manager.conversation_history[-100:])  # 永久记忆时使用全部历史，否则保留最近100轮对话

                response = self.ai_manager.client.chat.completions.create(
                    model=self.ai_manager.MODEL,
                    messages=messages,
                    temperature=0.8,
                    max_tokens=self.max_tokens,
                    stream=True,
                    extra_body={"thinking": {"type": "disabled"}}
                )

                # 流式收集完整内容
                full_content = ""
                for chunk in response:
                    if not self._is_running:
                        break
                    # 检查超时
                    if time.time() - self._start_time > 20:
                        self.error_occurred.emit("timeout")
                        return
                    if chunk.choices and chunk.choices[0].delta.content:
                        full_content += chunk.choices[0].delta.content

                if not self._is_running:
                    return

                # 解析：[表情]日语|中文
                emotion = "normal"
                japanese_text = ""
                chinese_text = ""

                try:
                    import re
                    print(f"[音频模式] 完整内容: {full_content}")
                    
                    # 处理多个表情标签
                    # 提取最后一个表情标签（因为它是最新的）
                    emotion_matches = re.findall(r'\[([^\]]+)\]', full_content)
                    if emotion_matches:
                        emotion = emotion_matches[-1]  # 使用最后一个表情标签
                        # 移除所有表情标签
                        full_content = re.sub(r'\[[^\]]+\]', '', full_content).strip()
                        print(f"[音频模式] 提取表情: {emotion}, 剩余内容: {full_content}")

                    if '|' in full_content:
                        parts = full_content.split('|', 1)
                        japanese_text = parts[0].strip()
                        chinese_text = parts[1].strip() if len(parts) > 1 else ""
                        print(f"[音频模式] 分割结果 - 日语: {japanese_text}, 中文: {chinese_text}")
                    else:
                        # 如果没有分隔符，尝试检测语言
                        # 简单的语言检测：如果包含日语字符，当作日语并翻译
                        has_japanese = bool(re.search(r'[\u3040-\u30ff\u3400-\u4dbf\u4e00-\u9fff\uff66-\uff9f]', full_content))
                        if has_japanese:
                            japanese_text = full_content
                            chinese_text = self.ai_manager._translate_to_chinese(japanese_text)
                        else:
                            # 否则当作中文
                            chinese_text = full_content
                            japanese_text = self.ai_manager._translate_to_japanese(chinese_text)
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

                # 先显示日语文本
                self.japanese_text_ready.emit(japanese_text)

                # 在后台线程中生成音频，不阻塞中文文本显示
                audio_path = None
                if japanese_text and self._is_running:
                    # 检查超时
                    if time.time() - self._start_time > 20:
                        self.error_occurred.emit("timeout")
                        return
                    
                    # 使用QTimer在后台生成音频
                    import tempfile
                    from pathlib import Path
                    
                    def generate_audio_async():
                        try:
                            print(f"[音频生成] 开始生成音频")
                            audio_url = self.audio_generator.generate_audio(
                                text=japanese_text,
                                voice_id=self.voice_id,
                                language="ja"
                            )
                            
                            if audio_url:
                                print(f"[音频生成] 获得音频URL: {audio_url}")
                                # 直接发射信号（PyQt信号是线程安全的）
                                self.audio_ready.emit(audio_url)
                            else:
                                print(f"[音频生成] 音频URL为空")
                                self.audio_status.emit("音频生成失败")
                        except Exception as e:
                            print(f"[音频生成] 异常: {e}")
                            import traceback
                            traceback.print_exc()
                            self.audio_status.emit("音频生成失败")
                    
                    # 创建并启动后台线程
                    audio_thread = threading.Thread(target=generate_audio_async, daemon=True)
                    audio_thread.start()

                # 立即流式显示中文文本（不等待音频生成）
                if self._is_running:
                    for char in chinese_text:
                        if not self._is_running:
                            break
                        self.chunk_ready.emit(char)
                        self.msleep(25)

                # 添加到历史
                self.ai_manager.conversation_history.append({"role": "assistant", "content": chinese_text})
                
                # 等待音频线程完成
                if 'audio_thread' in locals() and audio_thread.is_alive():
                    audio_thread.join(timeout=30)
                
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
                    if time.time() - self._start_time > 20:
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


class ChatWidget(QWidget):
    """聊天界面组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ai_manager = None  # 延迟初始化
        self.audio_generator = None  # 延迟初始化
        self.vocu_voice_id = None
        self.current_worker = None  # 当前工作线程
        self.current_streaming_text = ""  # 当前流式显示的文本
        self.permanent_memory = False  # 永久记忆功能
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 聊天历史显示区
        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        self.chat_history.setStyleSheet("""
            QTextEdit {
                background-color: rgba(255, 255, 255, 200);
                border-radius: 10px;
                padding: 10px;
                font-size: 14px;
            }
        """)
        layout.addWidget(self.chat_history)
        
        # 输入区域
        input_layout = QHBoxLayout()

        # 附件按钮
        self.attach_button = QPushButton("📎")
        self.attach_button.setFixedSize(40, 40)
        self.attach_button.setStyleSheet("""
            QPushButton {
                padding: 5px;
                border-radius: 20px;
                background-color: #8B4513;
                color: white;
                font-size: 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
        """)
        self.attach_button.setToolTip("上传图片")
        self.attach_button.clicked.connect(self.attach_image)
        input_layout.addWidget(self.attach_button)

        self.input_field = QLineEdit()
        self.input_field.setPlaceholderText("和牧濑红莉栖对话...")
        self.input_field.setStyleSheet("""
            QLineEdit {
                padding: 10px;
                border-radius: 20px;
                border: 2px solid #8B4513;
                background-color: white;
                color: #333333;
                font-size: 14px;
            }
            QLineEdit::placeholder {
                color: #888888;
            }
        """)
        self.input_field.returnPressed.connect(self.send_message)
        input_layout.addWidget(self.input_field)

        self.send_button = QPushButton("发送")
        self.send_button.setStyleSheet("""
            QPushButton {
                padding: 10px 20px;
                border-radius: 20px;
                background-color: #8B4513;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
        """)
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        layout.addLayout(input_layout)

        # 当前附加的图片
        self.attached_image_path = None
    
    def init_resources(self):
        """初始化资源（异步调用）"""
        print("[初始化] 开始初始化资源...")
        
        # 加载模型设置
        from PyQt6.QtCore import QSettings
        qsettings = QSettings("AMDS", "Amadeus")
        model_type = qsettings.value("model_type", "默认")
        custom_model_url = qsettings.value("custom_model_url", "http://localhost:11434")
        custom_model_name = qsettings.value("custom_model_name", "")
        
        # 加载永久记忆设置
        self.permanent_memory = qsettings.value("permanent_memory", False, type=bool)
        print(f"[初始化] 永久记忆功能: {'启用' if self.permanent_memory else '禁用'}")
        
        # 初始化AI管理器（不加载历史，延迟加载）
        self.ai_manager = AIChatManager(model_type, custom_model_url, custom_model_name, load_history=False)
        saved_key = AIChatManager.load_api_key()
        if saved_key and model_type != "自定义":
            self.ai_manager.API_KEY = saved_key
            from openai import OpenAI
            self.ai_manager.client = OpenAI(
                base_url=self.ai_manager.BASE_URL,
                api_key=saved_key
            )
            print(f"[初始化] 已加载保存的API密钥")
        elif model_type == "自定义":
            print(f"[初始化] 使用自定义模型: {custom_model_name} at {custom_model_url}")
        
        # 延迟加载对话历史（主窗口显示后）
        if self.permanent_memory:
            from PyQt6.QtCore import QTimer
            QTimer.singleShot(1000, self.load_conversation_history)
        
        # 延迟初始化音频生成器（主窗口显示后）
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(1500, self._init_audio_generator)
        
        print("[初始化] 基本资源初始化完成")
    
    def load_conversation_history(self):
        """延迟加载对话历史"""
        if self.ai_manager and self.permanent_memory:
            print("[延迟加载] 开始加载对话历史...")
            self.ai_manager.load_conversation()
            if self.ai_manager.conversation_history:
                print(f"[延迟加载] 显示 {len(self.ai_manager.conversation_history)} 条对话历史")
                for message in self.ai_manager.conversation_history:
                    if message["role"] == "user":
                        self.add_message("你", message["content"], "#0066CC")
                    elif message["role"] == "assistant":
                        self.add_message("牧濑红莉栖", message["content"], "#8B4513")
            print("[延迟加载] 对话历史加载完成")

    def _init_audio_generator(self):
        """初始化音频生成器"""
        # 使用QSettings加载Vocu设置
        from PyQt6.QtCore import QSettings
        qsettings = QSettings("AMDS", "Amadeus")
        
        print(f"初始化音频生成器，使用QSettings")

        try:
            vocu_api_key = qsettings.value("vocu_api_key", "")
            self.vocu_voice_id = qsettings.value("vocu_voice_id", "")
            self.audio_mode = qsettings.value("audio_mode", True, type=bool)
            self.max_tokens = qsettings.value("max_tokens", 200, type=int)

            print(f"加载Vocu配置: api_key={'*' * len(vocu_api_key) if vocu_api_key else '空'}, voice_id={self.vocu_voice_id or '空'}, audio_mode={self.audio_mode}, max_tokens={self.max_tokens}")

            if vocu_api_key and self.audio_mode:
                from audiogenerate import VocuAudioGenerator
                self.audio_generator = VocuAudioGenerator(vocu_api_key)
                print(f"已初始化音频生成器")
            else:
                self.audio_generator = None
                if not self.audio_mode:
                    print(f"音频模式已关闭")
                else:
                    print(f"未配置Vocu API密钥，音频生成器未初始化")
        except Exception as e:
            print(f"加载音频配置失败: {e}")
            import traceback
            traceback.print_exc()
            # 设置默认值
            self.audio_generator = None
            self.audio_mode = True
            self.max_tokens = 200

    def attach_image(self):
        """选择图片附件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择图片",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.gif)"
        )
        if file_path:
            self.attached_image_path = file_path
            # 在输入框显示提示
            self.input_field.setPlaceholderText(f"已选择图片: {Path(file_path).name} (输入文字后发送)")
            print(f"已选择图片: {file_path}")

    def send_message(self):
        """发送消息 - 智能选择预设回复或AI生成"""
        text = self.input_field.text().strip()
        if not text and not self.attached_image_path:
            return

        # 禁用输入
        self.input_field.setEnabled(False)
        self.send_button.setEnabled(False)
        self.attach_button.setEnabled(False)

        # 显示用户消息（包含图片）
        if self.attached_image_path:
            self.add_message_with_image("你", text or "", "#4169E1", self.attached_image_path)
        else:
            self.add_message("你", text, "#4169E1")

        # 获取所有匹配的预设语音
        matching_presets = VoiceDialog.get_all_matching_responses(text)
        has_preset = matching_presets and matching_presets != VoiceDialog.RESPONSES["default"]

        # 判断是否启用音频生成
        enable_audio = (self.audio_mode and
                       self.audio_generator is not None and
                       self.vocu_voice_id is not None)
        
        print(f"[音频模式] self.audio_mode={self.audio_mode}, audio_generator={self.audio_generator is not None}, vocu_voice_id={self.vocu_voice_id is not None}, enable_audio={enable_audio}")

        # 30%概率使用预设，70%概率使用AI生成（有图片或启用音频时不使用预设）
        if has_preset and random.random() < 0.3 and not self.attached_image_path and not enable_audio:
            # 使用AI智能选择最佳预设
            self._use_ai_selected_preset(text, matching_presets)
        else:
            # 使用AI生成回复 - 流式传输
            self._use_ai_response_streaming(text, self.attached_image_path, enable_audio)

        # 清空输入和附件
        self.input_field.clear()
        self.attached_image_path = None
        self.input_field.setPlaceholderText("和牧濑红莉栖对话...")
    
    def _use_ai_selected_preset(self, user_text: str, available_presets: list):
        """使用AI智能选择预设语音"""
        # 在后台线程中选择预设
        class PresetSelectorWorker(QThread):
            preset_selected = pyqtSignal(str)  # 选中的预设
            error_occurred = pyqtSignal()
            
            def __init__(self, ai_manager, user_text, presets):
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
        
        self.current_worker = PresetSelectorWorker(self.ai_manager, user_text, available_presets)
        self.current_worker.preset_selected.connect(lambda preset: self._on_preset_selected(preset))
        self.current_worker.error_occurred.connect(lambda: self._on_preset_selected(random.choice(available_presets)))
        self.current_worker.start()
    
    def _on_preset_selected(self, preset_audio: str):
        """AI选择预设后的回调"""
        # 使用打字机效果显示
        response_text = self.get_response_text(preset_audio)
        emotion = VoiceDialog.get_emotion_for_audio(preset_audio)
        
        # 先添加空的消息占位
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")
        
        # 创建打字机效果线程
        self.current_worker = TypewriterWorker(response_text, emotion, char_delay=60)
        self.current_worker.char_ready.connect(self._on_streaming_char)
        self.current_worker.typing_complete.connect(self._on_preset_streaming_complete)
        self.current_worker.start()
        
        # 播放音频
        self.play_audio(preset_audio, getattr(self, 'character', None))
    
    def _use_preset_response_streaming(self, audio_name: str):
        """使用预设语音回复 - 打字机效果"""
        response_text = self.get_response_text(audio_name)
        emotion = VoiceDialog.get_emotion_for_audio(audio_name)
        
        # 先添加空的消息占位
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")

        # 创建打字机效果线程
        self.current_worker = TypewriterWorker(response_text, emotion, char_delay=60)
        self.current_worker.char_ready.connect(self._on_streaming_char)
        self.current_worker.typing_complete.connect(self._on_preset_streaming_complete)
        self.current_worker.start()

        # 播放音频
        self.play_audio(audio_name, getattr(self, 'character', None))
    
    def _use_ai_response_streaming(self, user_text: str, image_path: str = None, enable_audio: bool = False):
        """使用AI生成回复 - 流式传输，支持图片和音频"""
        # 先添加空的消息占位
        self.current_streaming_text = ""
        self._append_streaming_prefix("牧濑红莉栖", "#8B4513")

        # 创建流式API线程 - 支持图片和音频
        voice_id = getattr(self, 'vocu_voice_id', None)
        audio_generator = getattr(self, 'audio_generator', None)
        max_tokens = getattr(self, 'max_tokens', 200)

        self.current_worker = ChatWorker(
            self.ai_manager, user_text, image_path,
            audio_generator=audio_generator,
            voice_id=voice_id,
            enable_audio=enable_audio,
            max_tokens=max_tokens
        )
        self.current_worker.emotion_ready.connect(self._on_emotion_ready)
        self.current_worker.chunk_ready.connect(self._on_streaming_chunk)
        self.current_worker.response_complete.connect(self._on_ai_streaming_complete)
        self.current_worker.error_occurred.connect(self._on_ai_error)
        self.current_worker.audio_status.connect(self._on_audio_status)
        self.current_worker.audio_ready.connect(self._on_audio_ready)
        self.current_worker.japanese_text_ready.connect(self._on_japanese_text_ready)
        self.current_worker.start()
    
    def _append_streaming_prefix(self, sender: str, color: str, show_loading: bool = True):
        """添加流式消息的前缀 - 使用文本块方式，可选加载动画"""
        # 添加发送者前缀，不换行
        self.chat_history.append(
            f'<span style="color: {color}; font-weight: bold;">{sender}:</span> '
        )
        # 保存当前块位置用于后续追加
        self._streaming_block = self.chat_history.document().lastBlock()
        self._streaming_pos = len(self._streaming_block.text())

        # 启动加载动画
        if show_loading:
            self._loading_dots = 0
            self._loading_timer = QTimer(self)
            self._loading_timer.timeout.connect(self._update_loading_animation)
            self._loading_timer.start(500)  # 每500ms更新一次
            self._loading_active = True

    def _update_loading_animation(self):
        """更新加载动画（三个点循环）- 使用QTextCursor精确定位"""
        if not hasattr(self, '_loading_active') or not self._loading_active:
            return

        # 更新点的数量 (1 -> 2 -> 3 -> 1...)
        self._loading_dots = (self._loading_dots % 3) + 1
        dots = "." * self._loading_dots

        cursor = self.chat_history.textCursor()

        # 删除之前的加载点
        if hasattr(self, '_loading_start_pos') and hasattr(self, '_loading_end_pos'):
            cursor.setPosition(self._loading_start_pos)
            cursor.setPosition(self._loading_end_pos, cursor.MoveMode.KeepAnchor)
            cursor.removeSelectedText()

        # 在末尾插入新的加载点
        cursor.movePosition(cursor.MoveOperation.End)
        self._loading_start_pos = cursor.position()
        cursor.insertHtml(f'<span style="color: #888;">{dots}</span>')
        self._loading_end_pos = cursor.position()

        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _stop_loading_animation(self):
        """停止加载动画并清除加载点"""
        if hasattr(self, '_loading_timer') and self._loading_timer:
            self._loading_timer.stop()

        # 清除已显示的加载点
        if hasattr(self, '_loading_active') and self._loading_active:
            if hasattr(self, '_loading_start_pos') and hasattr(self, '_loading_end_pos'):
                cursor = self.chat_history.textCursor()
                cursor.setPosition(self._loading_start_pos)
                cursor.setPosition(self._loading_end_pos, cursor.MoveMode.KeepAnchor)
                cursor.removeSelectedText()

        self._loading_active = False
        self._loading_dots = 0
        if hasattr(self, '_loading_start_pos'):
            delattr(self, '_loading_start_pos')
        if hasattr(self, '_loading_end_pos'):
            delattr(self, '_loading_end_pos')

    def _on_streaming_char(self, char: str):
        """打字机效果 - 接收单个字符"""
        # 停止加载动画
        if hasattr(self, '_loading_active') and self._loading_active:
            self._stop_loading_animation()

        # 使用 QTextCursor 插入带颜色的字符
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        # 如果是第一个字符，先插入空格分隔
        if not self.current_streaming_text:
            cursor.insertHtml("&nbsp;")

        self.current_streaming_text += char
        # 使用HTML插入黑色文本
        char_escaped = char.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        cursor.insertHtml(f'<span style="color: #000000;">{char_escaped}</span>')

        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_streaming_chunk(self, chunk: str):
        """流式传输 - 接收文本片段"""
        # 停止加载动画
        if hasattr(self, '_loading_active') and self._loading_active:
            self._stop_loading_animation()

        # 检查是否是日语文本
        if chunk.startswith("[日语]"):
            japanese_text = chunk[4:].strip()  # 移除[日语]前缀
            print(f"[流式传输] 检测到日语文本: {japanese_text}")
            self._on_japanese_text_ready(japanese_text)
            return

        # 检查是否包含表情标签
        if '[' in chunk and ']' in chunk:
            import re
            match = re.search(r'\[([^\]]+)\]', chunk)
            if match:
                # 提取表情标签
                emotion = match.group(1)
                print(f"[流式传输] 检测到表情标签: {emotion}")
                # 更新表情
                self._on_emotion_ready(emotion)
                # 移除表情标签，只显示文本部分
                chunk = re.sub(r'^\[[^\]]+\]', '', chunk).strip()
                # 如果移除标签后没有文本，直接返回
                if not chunk:
                    return

        # 使用 QTextCursor 插入带颜色的文本片段
        cursor = self.chat_history.textCursor()
        cursor.movePosition(cursor.MoveOperation.End)

        # 如果是第一个片段，先插入空格分隔
        if not self.current_streaming_text:
            cursor.insertHtml("&nbsp;")

        self.current_streaming_text += chunk
        # 使用HTML插入黑色文本
        chunk_escaped = chunk.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
        cursor.insertHtml(f'<span style="color: #000000;">{chunk_escaped}</span>')

        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def _on_preset_streaming_complete(self, full_text: str, emotion: str):
        """预设回答打字机效果完成"""
        # 设置表情
        if hasattr(self, 'character') and self.character:
            self.character.set_emotion(emotion)

        # 将预设回复添加到AI对话历史，保持上下文连贯
        if hasattr(self, 'ai_manager') and self.ai_manager:
            self.ai_manager.conversation_history.append({"role": "assistant", "content": full_text})

        # 重新启用输入
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.attach_button.setEnabled(True)
        self.input_field.setFocus()

        self.current_streaming_text = ""
    
    def _on_emotion_ready(self, emotion: str):
        """表情已确定，立即切换"""
        print(f"[表情] _on_emotion_ready 被调用，表情: {emotion}")
        if hasattr(self, 'character') and self.character:
            print(f"[表情] character存在，设置表情")
            self.character.set_emotion(emotion)
        else:
            print(f"[表情] character不存在")

    def _on_audio_status(self, status: str):
        """音频生成状态更新"""
        print(f"[音频状态] {status}")

    def _on_audio_ready(self, audio_source: str):
        """音频准备好，开始播放（支持URL和本地文件）"""
        print(f"[音频播放] _on_audio_ready 被调用，音频源: {audio_source}")
        if audio_source:
            if audio_source.startswith('http://') or audio_source.startswith('https://'):
                print(f"[音频播放] 检测到URL，直接播放")
            else:
                print(f"[音频播放] 检测到本地文件，检查文件是否存在: {Path(audio_source).exists()}")
            self.play_vocu_audio(audio_source)
        else:
            print(f"[音频播放] 音频源为空")

    def _on_playback_state_changed(self, state):
        """播放状态变化时处理"""
        print(f"[播放状态] 状态变化: {state}, PlayingState: {QMediaPlayer.PlaybackState.PlayingState}")
        
        if state == QMediaPlayer.PlaybackState.PlayingState:
            # 音频开始播放，启动说话动画
            if hasattr(self, 'character') and self.character and not self.character.is_speaking:
                print(f"[表情] 音频开始播放，启动说话动画")
                self.character.start_speaking()
        elif state == QMediaPlayer.PlaybackState.StoppedState:
            # 音频停止播放，停止说话动画
            if hasattr(self, 'character') and self.character and self.character.is_speaking:
                print(f"[表情] 音频停止播放，停止说话动画")
                self.character.stop_speaking()

    def _on_japanese_text_ready(self, japanese_text: str):
        """日语文本准备好，显示在人物下方"""
        print(f"[调试] _on_japanese_text_ready 被调用, 日语文本: {japanese_text}")
        print(f"[调试] hasattr(self, 'character')={hasattr(self, 'character')}, hasattr(self, 'audio_mode')={hasattr(self, 'audio_mode')}")
        if hasattr(self, 'audio_mode'):
            print(f"[调试] self.audio_mode={self.audio_mode}")
        
        if hasattr(self, 'character') and self.character:
            self.character.set_japanese_text(japanese_text)
            
            # 只在非音频模式下启动说话动画
            # 音频模式下，张嘴动画在音频播放时启动
            print(f"[音频模式检查] hasattr(self, 'audio_mode')={hasattr(self, 'audio_mode')}, self.audio_mode={getattr(self, 'audio_mode', 'N/A')}")
            
            if hasattr(self, 'audio_mode') and not self.audio_mode:
                print(f"[表情] 非音频模式，启动说话动画")
                try:
                    self.character.start_speaking()
                    
                    # 固定播放3秒的说话动画
                    duration = 3000
                    print(f"[表情] 说话动画持续时间: {duration}ms")
                    
                    def stop_speaking():
                        print(f"[表情] 停止说话动画")
                        if hasattr(self, 'character') and self.character:
                            self.character.stop_speaking()
                    QTimer.singleShot(duration, stop_speaking)
                except Exception as e:
                    print(f"[表情] 非音频模式说话动画异常: {e}")
                    import traceback
                    traceback.print_exc()
            else:
                print(f"[表情] 音频模式，不启动说话动画")

    def _on_ai_streaming_complete(self, full_text: str, emotion: str, audio_path: str = ""):
        """AI流式传输完成"""

        # 重新启用输入
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.attach_button.setEnabled(True)
        self.input_field.setFocus()

        self.current_streaming_text = ""
        
        # 保存对话历史（如果启用了永久记忆）
        if self.permanent_memory and self.ai_manager:
            self.ai_manager.save_conversation()

    def _on_ai_error(self, error_msg: str):
        """AI调用出错时的回调"""
        if error_msg == "timeout":
            # 显示超时消息
            timeout_message = "不好意思，我想我这边网络有点问题，我们稍后再聊这个话题吧"
            self.current_streaming_text += f"\n{timeout_message}"
        else:
            self.current_streaming_text += f"\n[错误: {error_msg}]"
        
        # 使用QTextCursor更新显示
        try:
            cursor = self.chat_history.textCursor()
            cursor.movePosition(cursor.MoveOperation.End)
            error_escaped = self.current_streaming_text.replace("<", "&lt;").replace(">", "&gt;").replace("&", "&amp;")
            cursor.insertHtml(f'<span style="color: #FF0000;">{error_escaped}</span>')
            # 滚动到底部
            scrollbar = self.chat_history.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            print(f"更新错误显示失败: {e}")

        # 重新启用输入
        self.input_field.setEnabled(True)
        self.send_button.setEnabled(True)
        self.attach_button.setEnabled(True)
        self.input_field.setFocus()
    
    def add_message(self, sender: str, text: str, color: str):
        """添加完整消息到历史 - 人名用指定颜色，文本用黑色"""
        self.chat_history.append(
            f'<span style="color: {color}; font-weight: bold;">{sender}:</span> '
            f'<span style="color: #000000;">{text}</span>'
        )
        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def add_message_with_image(self, sender: str, text: str, color: str, image_path: str):
        """添加带图片的消息到历史"""
        import base64
        # 读取图片并转为base64
        with open(image_path, 'rb') as f:
            img_data = base64.b64encode(f.read()).decode()

        # 获取图片格式
        ext = Path(image_path).suffix.lower()
        mime_type = {
            '.png': 'image/png',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.bmp': 'image/bmp',
            '.gif': 'image/gif'
        }.get(ext, 'image/png')

        # 构建HTML（限制图片最大宽度）
        html = f'<span style="color: {color}; font-weight: bold;">{sender}:</span>'
        if text:
            html += f' <span style="color: #000000;">{text}</span>'
        html += f'<br><img src="data:{mime_type};base64,{img_data}" style="max-width: 200px; max-height: 150px; border-radius: 5px; margin-top: 5px;">'

        self.chat_history.append(html)
        # 滚动到底部
        scrollbar = self.chat_history.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
    
    def get_response_text(self, audio_name: str) -> str:
        """根据音频文件名获取对应的文本 - 扩展版本"""
        text_map = {
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
            "memories_christina": "克里斯蒂娜的记忆...",
            "should_christina": "应该叫克里斯蒂娜吗...",
            
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
            "still_not_happy": "还是不太高兴。",
            
            # 疑问
            "huh_why_say": "嗯？为什么这么说？",
            "sounds_tough": "听起来很困难。",
            "humans_software": "人类就像软件一样。",
            
            # 记忆相关
            "memory_complex": "记忆是很复杂的。",
            "modifying_memories_impossible": "修改记忆是不可能的。",
            "secret_diary": "秘密日记...",
            
            # 变态相关
            "pervert_confirmed": "确认是变态。",
            "perverts_go_to_hell": "变态去死吧！",
            "pervert_idot_wanttodie": "你这个变态白痴，想死吗？",
            "devilish_pervert": "恶魔般的变态。",
            "this_guy_hopeless": "这家伙没救了。",
            
            # 前辈相关
            "senpai_question": "前辈？",
            "senpai_please_dont_tell": "前辈，请不要告诉别人...",
            "uh_senpai": "呃，前辈...",
            "senpai_who_is_this": "前辈，这是谁？",
            "senpai_what_we_talkin": "前辈，我们在说什么？",
            "senpai_questionmark": "前辈？？",
            "whats_so_funny_senpai": "前辈，有什么好笑的？",
            
            # 情绪表达
            "gah": "啊！",
            "gah_extended": "啊啊啊！",
            "daga_kotowaru": "但是我拒绝！",
            
            # 时间相关
            "tm_you_said": "你是说...",
            "tm_too_early": "太早了。",
            "tm_nonsense": "胡说八道。",
            "tm_not_possible": "不可能。",
            "tm_scientist_no_evidence": "科学家没有证据。",
            "tm_we_dont_know": "我们不知道。",

            # 其他
            "ask_me_whatever": "尽管问我任何事。",
            "happy": "开心~",
            "sad": "难过...",
            "angry": "生气！",
            "pissed": "愤怒！",
        }
        return text_map.get(audio_name, "...")
    
    def play_audio(self, audio_name: str, character=None):
        """播放音频 - 自动设置表情和动画"""
        audio_path = AUDIO_DIR / f"{audio_name}.ogg"
        if audio_path.exists():
            # 自动设置表情
            if character:
                emotion = VoiceDialog.get_emotion_for_audio(audio_name)
                character.set_emotion(emotion)
            
            self.player = AudioPlayer(audio_path)
            # 如果有角色组件，连接动画信号
            if character:
                self.player.started.connect(character.start_speaking)
                self.player.finished.connect(character.stop_speaking)
            self.player.start()
    
    def play_vocu_audio(self, audio_source: str):
        """播放Vocu生成的音频（支持URL和本地文件）"""
        try:
            if audio_source.startswith('http://') or audio_source.startswith('https://'):
                if not hasattr(self, 'media_player'):
                    self.media_player = QMediaPlayer()
                    self.audio_output = QAudioOutput()
                    self.media_player.setAudioOutput(self.audio_output)
                    self.audio_output.setVolume(1.0)  # 设置音量为最大
                    
                    # 优化缓冲设置，减少延迟
                    if hasattr(self.media_player, 'setBufferDuration'):
                        # 设置缓冲时长为最小值（100ms）
                        self.media_player.setBufferDuration(100)
                        print("[音频播放] 已设置最小缓冲时长")
                
                # 不在这里启动动画，而是在音频真正开始播放时启动
                # 连接播放状态变化信号
                if hasattr(self, 'character') and self.character:
                    print(f"[表情] 准备在音频播放时启动说话动画")
                    # 使用信号连接，在音频真正开始播放时启动动画
                    self.media_player.playbackStateChanged.connect(self._on_playback_state_changed)
                
                url = QUrl(audio_source)
                self.media_player.setSource(url)
                self.media_player.play()
                
                print(f"[音频播放] 直接播放URL: {audio_source}")
                
                # 增加一个计数器，避免立即停止动画
                check_count = 0
                max_checks = 30  # 最多检查30次（3秒）
                
                def check_audio_done():
                    nonlocal check_count
                    check_count += 1
                    
                    # 检查播放器状态
                    state = self.media_player.playbackState()
                    print(f"[音频检查] 第{check_count}次检查, 状态: {state}, PlayingState: {QMediaPlayer.PlaybackState.PlayingState}")
                    
                    # 如果不是播放状态，并且已经检查了多次，才停止动画
                    if state != QMediaPlayer.PlaybackState.PlayingState:
                        if check_count >= max_checks:
                            print(f"[表情] 停止说话动画（超时）")
                            if hasattr(self, 'character') and self.character:
                                self.character.stop_speaking()
                        else:
                            # 继续检查
                            QTimer.singleShot(100, check_audio_done)
                    else:
                        # 播放器正在播放，继续检查
                        QTimer.singleShot(100, check_audio_done)
                
                # 延迟开始检查，给播放器一些时间开始缓冲
                QTimer.singleShot(500, check_audio_done)
            else:
                import pygame
                pygame.mixer.init()
                pygame.mixer.music.load(str(audio_source))
                pygame.mixer.music.play()
                
                print(f"[音频播放] 播放本地文件: {audio_source}")
                
                if hasattr(self, 'character') and self.character:
                    print(f"[表情] 开始说话动画")
                    self.character.start_speaking()
                def check_audio_done():
                    if not pygame.mixer.music.get_busy():
                        print(f"[表情] 停止说话动画")
                        if hasattr(self, 'character') and self.character:
                            self.character.stop_speaking()
                    else:
                        QTimer.singleShot(100, check_audio_done)
                QTimer.singleShot(100, check_audio_done)
        except Exception as e:
            print(f"播放Vocu音频失败: {e}")
            import traceback
            traceback.print_exc()


class SettingsDialog(QDialog):
    """设置对话框 - 配置API密钥和音频设置"""

    def __init__(self, parent=None, current_api_key="", vocu_api_key="", vocu_voice_id="", audio_mode=True, current_max_tokens=500):
        super().__init__(parent)
        self.setWindowTitle("设置")

        # 设置样式
        self.setStyleSheet("""
            QDialog {
                background-color: #2C1810;
            }
            QLabel {
                color: #D2691E;
                font-size: 14px;
            }
            QLineEdit {
                padding: 8px;
                border-radius: 5px;
                border: 2px solid #8B4513;
                background-color: white;
                color: #333;
                min-width: 300px;
            }
            QComboBox {
                padding: 8px;
                border-radius: 5px;
                border: 2px solid #8B4513;
                background-color: white;
                color: #333;
                min-width: 300px;
            }
            QPushButton {
                padding: 10px 20px;
                border-radius: 5px;
                background-color: #8B4513;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
            QCheckBox {
                color: #D2691E;
                font-size: 14px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            QSlider {
                background-color: #8B4513;
            }
            QSlider::handle {
                background-color: #D2691E;
            }
        """)

        layout = QVBoxLayout(self)  # 使用垂直布局代替表单布局
        layout.setSpacing(15)
        layout.setContentsMargins(25, 25, 25, 25)
        
        # 创建网格布局用于模型设置
        model_layout = QGridLayout()
        model_layout.setColumnStretch(1, 1)
        model_layout.setHorizontalSpacing(10)
        model_layout.setVerticalSpacing(8)
        
        # 模型类型选择
        model_type_label = QLabel("模型类型:")
        model_type_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        model_type_label.setMinimumWidth(100)
        self.model_type_combo = QComboBox()
        model_types = ["默认", "自定义"]
        self.model_type_combo.addItems(model_types)
        model_layout.addWidget(model_type_label, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model_layout.addWidget(self.model_type_combo, 0, 1)
        
        # 模型选择（默认模式）
        default_model_label = QLabel("默认模型:")
        default_model_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        default_model_label.setMinimumWidth(100)
        self.model_combo = QComboBox()
        model_options = [
            "doubao-seed-1-6-lite-251015",
            "doubao-seed-1-8-251228",
            "doubao-seed-2-0-lite-260215",
            "doubao-seed-2-0-mini-260215",
            "doubao-seed-2-0-pro-260215"
        ]
        self.model_combo.addItems(model_options)
        model_layout.addWidget(default_model_label, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model_layout.addWidget(self.model_combo, 1, 1)
        
        # 自定义模型URL
        custom_url_label = QLabel("自定义模型URL:")
        custom_url_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        custom_url_label.setMinimumWidth(100)
        self.custom_model_url = QLineEdit()
        self.custom_model_url.setPlaceholderText("输入自定义模型URL（如 http://localhost:11434）")
        model_layout.addWidget(custom_url_label, 2, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model_layout.addWidget(self.custom_model_url, 2, 1)
        
        # 自定义模型名称
        custom_name_label = QLabel("自定义模型名称:")
        custom_name_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        custom_name_label.setMinimumWidth(100)
        self.custom_model_name = QLineEdit()
        self.custom_model_name.setPlaceholderText("输入自定义模型名称（如 qwen3:8b, llama3, mistral 等）")
        model_layout.addWidget(custom_name_label, 3, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model_layout.addWidget(self.custom_model_name, 3, 1)
        
        from PyQt6.QtCore import QSettings
        qsettings = QSettings("AMDS", "Amadeus")
        current_model_type = qsettings.value("model_type", "默认")
        current_model = qsettings.value("model", "doubao-seed-1-6-lite-251015")
        current_custom_url = qsettings.value("custom_model_url", "http://localhost:11434")
        current_custom_name = qsettings.value("custom_model_name", "")
        
        if current_model_type in model_types:
            self.model_type_combo.setCurrentText(current_model_type)
        if current_model in model_options:
            self.model_combo.setCurrentText(current_model)
        self.custom_model_url.setText(current_custom_url)
        self.custom_model_name.setText(current_custom_name)
        
        # 创建API和Tokens布局
        api_tokens_layout = QGridLayout()
        api_tokens_layout.setColumnStretch(1, 1)
        api_tokens_layout.setHorizontalSpacing(10)
        api_tokens_layout.setVerticalSpacing(8)
        
        # API密钥输入
        api_key_label = QLabel("AI API密钥:")
        api_key_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        api_key_label.setMinimumWidth(100)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入火山方舟API密钥...")
        self.api_key_input.setText(current_api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_tokens_layout.addWidget(api_key_label, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        api_tokens_layout.addWidget(self.api_key_input, 0, 1)
        
        # 动态显示/隐藏模型选项
        def update_model_visibility():
            is_custom = self.model_type_combo.currentText() == "自定义"
            default_model_label.setVisible(not is_custom)
            self.model_combo.setVisible(not is_custom)
            custom_url_label.setVisible(is_custom)
            self.custom_model_url.setVisible(is_custom)
            custom_name_label.setVisible(is_custom)
            self.custom_model_name.setVisible(is_custom)
            # 当模型类型为自定义时，隐藏AI API密钥选项
            api_key_label.setVisible(not is_custom)
            self.api_key_input.setVisible(not is_custom)
        
        self.model_type_combo.currentTextChanged.connect(update_model_visibility)
        update_model_visibility()
        
        # 添加模型布局到主布局
        layout.addLayout(model_layout)
        
        # 分隔线
        line = QLabel("─" * 40)
        line.setStyleSheet("color: #8B4513;")
        line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(line)
        
        # Tokens长度滑块
        tokens_label = QLabel("最大Tokens长度:")
        tokens_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        tokens_label.setMinimumWidth(100)
        self.max_tokens_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_tokens_slider.setMinimum(50)
        self.max_tokens_slider.setMaximum(2000)
        self.max_tokens_slider.setValue(current_max_tokens)
        self.max_tokens_slider.setTickInterval(100)
        self.max_tokens_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.max_tokens_slider.setMinimumWidth(250)
        
        # 显示当前tokens值的标签
        self.max_tokens_label = QLabel(f"{current_max_tokens}")
        self.max_tokens_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.max_tokens_label.setFixedWidth(50)
        
        # 连接滑块信号，实时更新标签
        self.max_tokens_slider.valueChanged.connect(lambda value: self.max_tokens_label.setText(f"{value}"))
        
        # 创建水平布局来放置滑块和标签
        tokens_control_layout = QHBoxLayout()
        tokens_control_layout.addWidget(self.max_tokens_slider)
        tokens_control_layout.addWidget(self.max_tokens_label)
        
        tokens_control_widget = QWidget()
        tokens_control_widget.setLayout(tokens_control_layout)
        
        api_tokens_layout.addWidget(tokens_label, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        api_tokens_layout.addWidget(tokens_control_widget, 1, 1)
        
        # 添加API和Tokens布局到主布局
        layout.addLayout(api_tokens_layout)
        
        # 提示文字
        tokens_tip = QLabel('长度越长，生成时间越长，音频处理消耗点数越多。\n注意：50个tokens实际可能只有25-40个中文字符输出')
        tokens_tip.setStyleSheet('color: #888; font-size: 12px;')
        tokens_tip.setWordWrap(True)
        layout.addWidget(tokens_tip)
        
        # 分隔线
        line2 = QLabel("─" * 40)
        line2.setStyleSheet("color: #8B4513;")
        line2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(line2)
        
        # 音频模式开关
        self.audio_mode_checkbox = QCheckBox("启用音频模式（生成日语音频）")
        self.audio_mode_checkbox.setChecked(audio_mode)
        # 修改复选框样式，使钩和背景容易区分
        self.audio_mode_checkbox.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #FFFFFF;
                border-radius: 4px;
                background: #2C1810;
            }
            QCheckBox::indicator:checked {
                background: #FF6347;
                border-color: #FFFFFF;
            }
            QCheckBox::indicator:checked:hover {
                background: #FF6347;
            }
        """)
        layout.addWidget(self.audio_mode_checkbox)
        
        # 永久记忆功能开关（实验性）
        self.permanent_memory_checkbox = QCheckBox("启用永久记忆（实验性）")
        # 从QSettings加载永久记忆设置
        from PyQt6.QtCore import QSettings
        qsettings = QSettings("AMDS", "Amadeus")
        permanent_memory = qsettings.value("permanent_memory", False, type=bool)
        self.permanent_memory_checkbox.setChecked(permanent_memory)
        self.permanent_memory_checkbox.setStyleSheet("""
            QCheckBox {
                color: #FFFFFF;
                font-size: 13px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 2px solid #FFFFFF;
                border-radius: 4px;
                background: #2C1810;
            }
            QCheckBox::indicator:checked {
                background: #4CAF50;
                border-color: #FFFFFF;
            }
            QCheckBox::indicator:checked:hover {
                background: #4CAF50;
            }
        """)
        layout.addWidget(self.permanent_memory_checkbox)
        
        # 永久记忆功能说明
        memory_info = QLabel("开启后将永久保存对话历史，关闭软件后再打开仍能保持记忆。关闭此选项会清除所有历史记录并重启软件。（实际仍受限于上下文窗口，但256k的极限应该一时半会不会用完）")
        memory_info.setStyleSheet("color: #888; font-size: 11px;")
        memory_info.setWordWrap(True)
        layout.addWidget(memory_info)
        
        # 创建Vocu布局
        vocu_layout = QGridLayout()
        vocu_layout.setColumnStretch(1, 1)
        vocu_layout.setHorizontalSpacing(10)
        vocu_layout.setVerticalSpacing(8)
        
        # Vocu API密钥输入（日语音频生成）
        vocu_api_label = QLabel("Vocu API密钥:")
        vocu_api_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        vocu_api_label.setMinimumWidth(100)
        self.vocu_api_key_input = QLineEdit()
        self.vocu_api_key_input.setPlaceholderText("输入Vocu API密钥（可选，用于日语音频生成）...")
        self.vocu_api_key_input.setText(vocu_api_key)
        self.vocu_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        vocu_layout.addWidget(vocu_api_label, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vocu_layout.addWidget(self.vocu_api_key_input, 0, 1)
        
        # Vocu声音ID输入
        vocu_voice_label = QLabel("Vocu声音ID:")
        vocu_voice_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        vocu_voice_label.setMinimumWidth(100)
        self.vocu_voice_id_input = QLineEdit()
        self.vocu_voice_id_input.setPlaceholderText("输入Vocu声音ID（用于日语音频生成）...")
        self.vocu_voice_id_input.setText(vocu_voice_id)
        vocu_layout.addWidget(vocu_voice_label, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vocu_layout.addWidget(self.vocu_voice_id_input, 1, 1)
        
        # 点数显示
        self.credits_label = QLabel("点数: 查询中...")
        self.credits_label.setStyleSheet("color: #FFD700; font-size: 13px;")
        
        # 查询点数按钮
        self.refresh_credits_btn = QPushButton("刷新点数")
        self.refresh_credits_btn.clicked.connect(self._fetch_credits)
        
        # 说明文字
        self.vocu_info = QLabel("配置后可生成牧濑红莉栖的日语音频")
        self.vocu_info.setStyleSheet("color: #888; font-size: 11px;")
        
        # 动态显示/隐藏Vocu设置
        def update_audio_visibility():
            is_audio_enabled = self.audio_mode_checkbox.isChecked()
            vocu_api_label.setVisible(is_audio_enabled)
            self.vocu_api_key_input.setVisible(is_audio_enabled)
            vocu_voice_label.setVisible(is_audio_enabled)
            self.vocu_voice_id_input.setVisible(is_audio_enabled)
            self.credits_label.setVisible(is_audio_enabled)
            self.refresh_credits_btn.setVisible(is_audio_enabled)
            self.vocu_info.setVisible(is_audio_enabled)
        
        self.audio_mode_checkbox.stateChanged.connect(update_audio_visibility)
        update_audio_visibility()
        
        # 添加Vocu布局到主布局
        layout.addLayout(vocu_layout)
        layout.addWidget(self.credits_label)
        layout.addWidget(self.refresh_credits_btn)
        layout.addWidget(self.vocu_info)

        # 项目GitHub地址
        github_link = QLabel('项目地址：<a href="https://github.com/Kur1oR3iko/AMDS-RE">https://github.com/Kur1oR3iko/AMDS-RE</a>')
        github_link.setStyleSheet("color: #4A90E2; font-size: 11px;")
        github_link.setOpenExternalLinks(True)
        layout.addWidget(github_link)
        
        # 作者信息
        author_info = QLabel('b站/抖音"栗尾玲子Reiko"最新力作')
        author_info.setStyleSheet("color: #888; font-size: 12px; margin-top: 8px;")
        author_info.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(author_info)
        
        # 水友群信息
        group_info = QLabel('水友群1:391437320，2群852680622')
        group_info.setStyleSheet("color: #888; font-size: 12px; margin-top: 2px;")
        group_info.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(group_info)

        # 按钮区域
        button_layout = QHBoxLayout()

        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.accept)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)
        
        # 调整大小以适应内容
        self.adjustSize()
        
        # 连接信号，当内容变化时重新调整大小
        def adjust_dialog_size():
            # 先隐藏所有动态元素
            default_model_label.setVisible(False)
            self.model_combo.setVisible(False)
            custom_url_label.setVisible(False)
            self.custom_model_url.setVisible(False)
            custom_name_label.setVisible(False)
            self.custom_model_name.setVisible(False)
            api_key_label.setVisible(False)
            self.api_key_input.setVisible(False)
            
            # 显示当前应该显示的元素
            is_custom = self.model_type_combo.currentText() == "自定义"
            is_audio = self.audio_mode_checkbox.isChecked()
            
            if not is_custom:
                default_model_label.setVisible(True)
                self.model_combo.setVisible(True)
                api_key_label.setVisible(True)
                self.api_key_input.setVisible(True)
            else:
                custom_url_label.setVisible(True)
                self.custom_model_url.setVisible(True)
                custom_name_label.setVisible(True)
                self.custom_model_name.setVisible(True)
            
            # 调整大小
            self.adjustSize()
        
        self.model_type_combo.currentTextChanged.connect(adjust_dialog_size)
        self.audio_mode_checkbox.stateChanged.connect(adjust_dialog_size)

        # 延迟查询点数，避免阻塞对话框显示
        from PyQt6.QtCore import QTimer
        QTimer.singleShot(100, self._fetch_credits)

    def _fetch_credits(self):
        """获取Vocu账户点数"""
        vocu_api_key = self.vocu_api_key_input.text().strip()
        if not vocu_api_key:
            self.credits_label.setText("点数: 请先输入API密钥")
            return

        import requests
        try:
            response = requests.get(
                "https://v1.vocu.studio/api/account/info",
                headers={
                    "Authorization": f"Bearer {vocu_api_key}",
                    "Content-Type": "application/json"
                },
                timeout=10,
                verify=False
            )
            data = response.json()
            if data.get("status") == 200:
                credits = data.get("user", {}).get("credits", 0)
                self.credits_label.setText(f"点数: {credits}")
                self.credits_label.setStyleSheet("color: #00FF00; font-size: 13px;")
            else:
                self.credits_label.setText(f"点数: 查询失败")
                self.credits_label.setStyleSheet("color: #FF6347; font-size: 13px;")
        except Exception as e:
            self.credits_label.setText(f"点数: 查询失败")
            self.credits_label.setStyleSheet("color: #FF6347; font-size: 13px;")

    def get_settings(self):
        """获取设置值"""
        return {
            "api_key": self.api_key_input.text().strip(),
            "model_type": self.model_type_combo.currentText(),
            "model": self.model_combo.currentText(),
            "custom_model_url": self.custom_model_url.text().strip(),
            "custom_model_name": self.custom_model_name.text().strip(),
            "vocu_api_key": self.vocu_api_key_input.text().strip(),
            "vocu_voice_id": self.vocu_voice_id_input.text().strip(),
            "audio_mode": self.audio_mode_checkbox.isChecked(),
            "permanent_memory": self.permanent_memory_checkbox.isChecked(),
            "max_tokens": self.max_tokens_slider.value()
        }


class MainWindow(QMainWindow):
    """主窗口"""
    
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Amadeus - 牧濑红莉栖")
        self.setMinimumSize(900, 600)
        
        # 设置窗口图标
        icon_path = IMAGES_DIR / "ic_launcher.png"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        
        # 设置窗口样式
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2C1810;
            }
        """)
        
        self.setup_ui()
    
    def setup_ui(self):
        """设置UI"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 主布局
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(20, 20, 20, 20)
        
        # 左侧：角色显示（自动表情，无按钮）
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        self.character = KurisuCharacter()
        left_layout.addWidget(self.character, alignment=Qt.AlignmentFlag.AlignCenter)
        
        main_layout.addWidget(left_panel, 1)
        
        # 右侧：聊天区域
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # 标题区域 - 带Logo和设置按钮
        title_widget = QWidget()
        title_layout = QHBoxLayout(title_widget)
        title_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Logo图片
        self.logo_label = QLabel()
        logo_pixmap = QPixmap(str(IMAGES_DIR / "logo1.png"))
        if not logo_pixmap.isNull():
            scaled_logo = logo_pixmap.scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            self.logo_label.setPixmap(scaled_logo)
        title_layout.addWidget(self.logo_label)

        # 标题文字
        title = QLabel("Amadeus System")
        title.setStyleSheet("""
            QLabel {
                color: #D2691E;
                font-size: 24px;
                font-weight: bold;
                padding: 10px;
            }
        """)
        title_layout.addWidget(title)

        # 设置按钮（使用logo39作为图标）- 96x96
        self.settings_button = QPushButton()
        settings_pixmap = QPixmap(str(IMAGES_DIR / "logo39.png"))
        if not settings_pixmap.isNull():
            scaled_pixmap = settings_pixmap.scaled(96, 96, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
            settings_icon = QIcon(scaled_pixmap)
            self.settings_button.setIcon(settings_icon)
            self.settings_button.setIconSize(scaled_pixmap.size())
        self.settings_button.setFixedSize(120, 120)
        self.settings_button.setStyleSheet("""
            QPushButton {
                background-color: transparent;
                border: none;
            }
            QPushButton:hover {
                background-color: rgba(139, 69, 19, 0.3);
                border-radius: 5px;
            }
        """)
        self.settings_button.setToolTip("设置")
        self.settings_button.clicked.connect(self.open_settings)
        title_layout.addWidget(self.settings_button)

        right_layout.addWidget(title_widget)
        
        # 聊天组件 - 传递角色组件用于动画控制
        self.chat = ChatWidget()
        self.chat.character = self.character  # 让chat可以访问角色
        right_layout.addWidget(self.chat, 1)
        
        main_layout.addWidget(right_panel, 2)
    
    def play_tone(self):
        """播放启动音效 tone.ogg"""
        print("[启动] 开始播放启动音效...")
        tone_path = AUDIO_DIR / "tone.ogg"
        print(f"[启动] 启动音效路径: {tone_path}")
        print(f"[启动] 启动音效文件存在: {tone_path.exists()}")
        if tone_path.exists():
            print("[启动] 创建AudioPlayer实例...")
            self.tone_player = AudioPlayer(tone_path)
            # 连接完成信号，播放完启动音后再播放问候语
            print("[启动] 连接完成信号...")
            self.tone_player.finished.connect(self.play_greeting)
            print("[启动] 开始播放启动音效...")
            self.tone_player.start()
        else:
            print("[启动] 启动音效文件不存在")

    def play_greeting(self):
        """播放问候语 - 带动画和聊天显示"""
        print("[启动] 开始播放问候语...")
        # 如果启用了永久记忆，不播放欢迎语
        if self.chat.permanent_memory:
            print("[启动] 永久记忆功能已启用，跳过欢迎语")
            return
        
        print("[启动] 获取随机问候语...")
        greeting = VoiceDialog.get_random_greeting()
        print(f"[启动] 随机问候语: {greeting}")

        # 在聊天框显示问候语
        print("[启动] 获取问候语文本...")
        greeting_text = self.chat.get_response_text(greeting)
        print(f"[启动] 问候语文本: {greeting_text}")
        self.chat.add_message("牧濑红莉栖", greeting_text, "#8B4513")

        # 播放语音
        audio_path = AUDIO_DIR / f"{greeting}.ogg"
        print(f"[启动] 问候语音频路径: {audio_path}")
        print(f"[启动] 问候语音频文件存在: {audio_path.exists()}")
        if audio_path.exists():
            # 自动设置表情
            print("[启动] 获取表情...")
            emotion = VoiceDialog.get_emotion_for_audio(greeting)
            print(f"[启动] 表情: {emotion}")
            self.character.set_emotion(emotion)

            print("[启动] 创建AudioPlayer实例...")
            self.player = AudioPlayer(audio_path)
            # 连接动画信号
            print("[启动] 连接动画信号...")
            self.player.started.connect(self.character.start_speaking)
            self.player.finished.connect(self.character.stop_speaking)
            print("[启动] 开始播放问候语音频...")
            self.player.start()
        else:
            print("[启动] 问候语音频文件不存在")

    def open_settings(self):
        """打开设置对话框"""
        # 获取当前设置
        current_api_key = self.chat.ai_manager.API_KEY

        # 使用QSettings加载Vocu设置
        from PyQt6.QtCore import QSettings
        qsettings = QSettings("AMDS", "Amadeus")
        
        vocu_api_key = qsettings.value("vocu_api_key", "")
        vocu_voice_id = qsettings.value("vocu_voice_id", "")
        audio_mode = qsettings.value("audio_mode", True, type=bool)
        max_tokens = qsettings.value("max_tokens", 200, type=int)
        
        print(f"加载Vocu设置: api_key={'*' * len(vocu_api_key) if vocu_api_key else '空'}, voice_id={vocu_voice_id or '空'}, audio_mode={audio_mode}, max_tokens={max_tokens}")

        # 显示设置对话框
        dialog = SettingsDialog(self, current_api_key, vocu_api_key, vocu_voice_id, audio_mode, max_tokens)
        result = dialog.exec()
        print(f"设置对话框结果: {result}, Accepted={QDialog.DialogCode.Accepted}")

        if result == QDialog.DialogCode.Accepted:
            settings = dialog.get_settings()
            print(f"获取设置: api_key={'*' * len(settings['api_key']) if settings['api_key'] else '空'}, vocu_api_key={'*' * len(settings['vocu_api_key']) if settings['vocu_api_key'] else '空'}, vocu_voice_id={settings['vocu_voice_id'] or '空'}, audio_mode={settings['audio_mode']}, max_tokens={settings['max_tokens']}")

            # 更新AI管理器设置
            if settings["api_key"]:
                self.chat.ai_manager.API_KEY = settings["api_key"]
                # 保存到本地文件
                self._save_api_key(settings["api_key"])

            # 更新模型和模型类型
            self.chat.ai_manager.MODEL = settings["model"]
            print(f"模型已更新为: {settings['model']}")

            # 重新初始化OpenAI客户端
            if settings["model_type"] == "自定义":
                # 保存当前对话历史
                current_history = self.chat.ai_manager.conversation_history if hasattr(self.chat.ai_manager, 'conversation_history') else []
                # 使用自定义模型
                self.chat.ai_manager = AIChatManager(
                    model_type=settings["model_type"],
                    custom_model_url=settings["custom_model_url"],
                    custom_model_name=settings["custom_model_name"]
                )
                # 恢复对话历史
                self.chat.ai_manager.conversation_history = current_history
                print(f"[设置] 已切换到自定义模型: {settings['custom_model_name']} at {settings['custom_model_url']}")
            else:
                # 使用默认模型
                self.chat.ai_manager.client = OpenAI(
                    base_url=self.chat.ai_manager.BASE_URL,
                    api_key=self.chat.ai_manager.API_KEY
                )
                print(f"[设置] 已切换到默认模型: {settings['model']}")

            # 处理永久记忆设置
            old_permanent_memory = self.chat.permanent_memory
            new_permanent_memory = settings.get("permanent_memory", False)
            
            # 保存Vocu设置（始终保存，包括清空的情况）
            print(f"保存Vocu设置...")
            self._save_vocu_settings(
                settings["vocu_api_key"], 
                settings["vocu_voice_id"], 
                settings["audio_mode"], 
                settings["max_tokens"], 
                settings["model"], 
                settings["model_type"], 
                settings["custom_model_url"], 
                settings["custom_model_name"],
                new_permanent_memory
            )
            
            # 更新聊天组件和AI管理器的永久记忆设置
            self.chat.permanent_memory = new_permanent_memory
            if self.chat.ai_manager:
                self.chat.ai_manager.permanent_memory = new_permanent_memory
            
            # 处理永久记忆状态变化
            if old_permanent_memory and not new_permanent_memory:
                # 从开启变为关闭：显示确认对话框
                from PyQt6.QtWidgets import QMessageBox
                msg_box = QMessageBox(self)
                msg_box.setWindowTitle("确认关闭永久记忆")
                msg_box.setText("你之前所说的背负所有人的记忆，就是这么一回事吗？")
                
                # 添加自定义按钮
                confirm_button = msg_box.addButton("。。。", QMessageBox.ButtonRole.AcceptRole)
                cancel_button = msg_box.addButton("我不关闭了", QMessageBox.ButtonRole.RejectRole)
                
                msg_box.exec()
                
                # 检查用户选择
                if msg_box.clickedButton() == confirm_button:
                    # 确认关闭：清除对话历史并重启
                    print("永久记忆功能已关闭，正在清除对话历史...")
                    if self.chat.ai_manager:
                        self.chat.ai_manager.clear_conversation()
                    # 重启软件
                    import sys
                    import os
                    print("正在重启软件...")
                    QApplication.instance().quit()
                    # 重启当前进程
                    os.execv(sys.executable, [sys.executable] + sys.argv)
                else:
                    # 取消关闭：保持永久记忆开启
                    print("用户取消关闭永久记忆")
                    # 恢复永久记忆设置
                    new_permanent_memory = True
                    self.chat.permanent_memory = new_permanent_memory
                    if self.chat.ai_manager:
                        self.chat.ai_manager.permanent_memory = new_permanent_memory
                    # 重新保存设置
                    self._save_vocu_settings(
                        settings["vocu_api_key"], 
                        settings["vocu_voice_id"], 
                        settings["audio_mode"], 
                        settings["max_tokens"], 
                        settings["model"], 
                        settings["model_type"], 
                        settings["custom_model_url"], 
                        settings["custom_model_name"],
                        new_permanent_memory
                    )
            elif not old_permanent_memory and new_permanent_memory:
                # 从关闭变为开启：加载对话历史
                print("永久记忆功能已开启，正在加载对话历史...")
                if self.chat.ai_manager:
                    self.chat.ai_manager.load_conversation()
            
            # 重新初始化音频生成器
            self.chat._init_audio_generator()

            print(f"设置已更新: API密钥已{'保存' if settings['api_key'] else '清空'}")

    def _save_api_key(self, api_key: str):
        """保存API密钥到本地文件"""
        try:
            config_dir = Path.home() / ".amadeus"
            config_dir.mkdir(exist_ok=True)
            config_file = config_dir / "config.json"
            with open(config_file, 'w', encoding='utf-8') as f:
                json.dump({"api_key": api_key}, f)
        except Exception as e:
            print(f"保存配置失败: {e}")

    def _load_api_key(self) -> str:
        """从本地文件加载API密钥"""
        try:
            config_file = Path.home() / ".amadeus" / "config.json"
            if config_file.exists():
                with open(config_file, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    return config.get("api_key", "")
        except Exception as e:
            print(f"加载配置失败: {e}")
        return ""

    def _save_vocu_settings(self, api_key: str, voice_id: str, audio_mode: bool = True, max_tokens: int = 500, model: str = "doubao-seed-1-6-lite-251015", model_type: str = "默认", custom_model_url: str = "http://localhost:11434", custom_model_name: str = "", permanent_memory: bool = False):
        """保存Vocu设置到QSettings"""
        from PyQt6.QtCore import QSettings
        
        try:
            qsettings = QSettings("AMDS", "Amadeus")
            
            qsettings.setValue("vocu_api_key", api_key)
            qsettings.setValue("vocu_voice_id", voice_id)
            qsettings.setValue("audio_mode", audio_mode)
            qsettings.setValue("max_tokens", max_tokens)
            qsettings.setValue("model", model)
            qsettings.setValue("model_type", model_type)
            qsettings.setValue("custom_model_url", custom_model_url)
            qsettings.setValue("custom_model_name", custom_model_name)
            qsettings.setValue("permanent_memory", permanent_memory)
            
            qsettings.sync()
            
            print(f"Vocu配置已保存: api_key={'*' * len(api_key) if api_key else '空'}, voice_id={voice_id or '空'}, audio_mode={audio_mode}, max_tokens={max_tokens}, model={model}, model_type={model_type}, custom_model_url={custom_model_url}, custom_model_name={custom_model_name}")
        except Exception as e:
            print(f"保存Vocu配置失败: {e}")
            import traceback
            traceback.print_exc()


class SplashScreen(QMainWindow):
    """启动动画窗口 - 使用Logo序列"""
    
    def __init__(self):
        super().__init__()
        
        # 设置窗口属性
        self.setWindowTitle("Amadeus")
        self.setFixedSize(250, 300)
        self.setStyleSheet("background-color: #1a1a2e;")
        
        # Logo标签
        self.logo_label = QLabel()
        self.logo_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        # 居中显示
        screen = QApplication.primaryScreen().geometry()
        self.move(
            (screen.width() - self.width()) // 2,
            (screen.height() - self.height()) // 2
        )
        
        # 主布局
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.logo_label)
        
        # 加载文字
        self.loading_text = QLabel("Loading Amadeus System...")
        self.loading_text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.loading_text.setStyleSheet("""
            QLabel {
                color: #D2691E;
                font-size: 16px;
                font-weight: bold;
                margin-top: 20px;
            }
        """)
        layout.addWidget(self.loading_text)
        
        # 版本信息
        version = QLabel("v0.1.0")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        version.setStyleSheet("""
            QLabel {
                color: #8B4513;
                font-size: 12px;
                margin-top: 10px;
            }
        """)
        layout.addWidget(version)
        
        # 动画参数
        self.current_frame = 1
        self.total_frames = 39
        self.animation_speed = 80  # ms per frame
        
        # 启动动画
        self.start_animation()

    def start_animation(self):
        """开始Logo动画"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(self.animation_speed)
        self.update_frame()
    
    def update_frame(self):
        """更新动画帧"""
        logo_path = IMAGES_DIR / f"logo{self.current_frame}.png"
        if logo_path.exists():
            pixmap = QPixmap(str(logo_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                self.logo_label.setPixmap(scaled)
        
        self.current_frame += 1
        if self.current_frame > self.total_frames:
            self.current_frame = 1  # 循环播放
    
    def stop_animation(self):
        """停止动画"""
        if hasattr(self, 'timer'):
            self.timer.stop()


def main():
    app = QApplication(sys.argv)
    
    # 设置应用样式
    app.setStyle("Fusion")
    
    # 显示启动动画
    splash = SplashScreen()
    splash.show()
    
    # 创建主窗口（但不显示）
    window = MainWindow()
    
    # 在后台线程中初始化资源
    import threading
    def init_resources():
        print("[启动] 开始异步初始化资源...")
        window.chat.init_resources()
        print("[启动] 资源初始化完成")
    
    init_thread = threading.Thread(target=init_resources, daemon=True)
    init_thread.start()
    
    # 2.5秒后关闭启动动画，显示主窗口
    def show_main_window():
        splash.stop_animation()
        splash.close()
        window.show()
        window.play_tone()  # 播放启动音效（问候语会在启动音播放完后自动播放）
    
    from PyQt6.QtCore import QTimer
    QTimer.singleShot(2500, show_main_window)
    
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
