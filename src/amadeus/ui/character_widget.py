"""
角色显示组件 - 牧濑红莉栖角色显示组件
"""
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QLabel, QScrollArea
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap

from ..utils import IMAGES_DIR
from ..constants import VALID_EMOTIONS


class KurisuCharacter(QWidget):
    """牧濑红莉栖角色显示组件 - 带背景，嘴部只在播放音频时动"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_emotion = "normal"
        self.animation_frame = 0
        self.is_speaking = False
        self.setup_ui()
        self.update_image()
    
    def setup_ui(self):
        """设置UI - 使用堆叠布局实现背景和角色的层级"""
        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.character_container = QWidget()
        self.character_container.setMinimumSize(438, 625)
        self.character_container.setMaximumSize(438, 625)

        self.bg_label = QLabel(self.character_container)
        self.bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_label.setGeometry(0, 0, 438, 625)
        self.load_background()

        self.image_label = QLabel(self.character_container)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setGeometry(32, 63, 375, 475)

        subtitle_frame_path = IMAGES_DIR / "subtitle_frame_big.png"
        if subtitle_frame_path.exists():
            print(f"[字幕背景] 找到图片: {subtitle_frame_path}")
            pixmap = QPixmap(str(subtitle_frame_path))
            if not pixmap.isNull():
                print(f"[字幕背景] 图片加载成功, 原始大小: {pixmap.width()}x{pixmap.height()}")
                scaled_pixmap = pixmap.scaled(
                    438, 75, 
                    Qt.AspectRatioMode.IgnoreAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                print(f"[字幕背景] 图片缩放后: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
                self.japanese_text_container = QLabel(self.character_container)
                self.japanese_text_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
                self.japanese_text_container.setGeometry(0, 520, 438, 75)
                self.japanese_text_container.setPixmap(scaled_pixmap)
                print(f"[字幕背景] 背景图片已设置")

                self._setup_text_scroll_area()
                
                # 将字幕背景放到最上层
                self.japanese_text_container.raise_()
                self.japanese_text_scroll.raise_()
            else:
                print(f"[字幕背景] 图片加载失败，使用备用模式")
                self._create_fallback_japanese_text_display()
        else:
            print(f"[字幕背景] 图片不存在: {subtitle_frame_path}，使用备用模式")
            self._create_fallback_japanese_text_display()

        # 将字幕背景放到最上层
        self.japanese_text_container.raise_()
        self.japanese_text_scroll.raise_()

        self.japanese_text_label.setText("")

        self.main_layout.addWidget(self.character_container, alignment=Qt.AlignmentFlag.AlignCenter)

    def _setup_text_scroll_area(self):
        """设置文本滚动区域"""
        self.japanese_text_scroll = QScrollArea(self.japanese_text_container)
        self.japanese_text_scroll.setGeometry(0, 0, 438, 75)
        self.japanese_text_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.japanese_text_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.japanese_text_scroll.setWidgetResizable(True)
        self.japanese_text_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.5);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: transparent;
                height: 0px;
            }
        """)

        scroll_content = QWidget()
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)

        self.japanese_text_label = QLabel()
        self.japanese_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.japanese_text_label.setWordWrap(True)
        self.japanese_text_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 15px;
                font-weight: bold;
                padding: 5px 8px;
                background: transparent;
            }
        """)

        scroll_layout.addWidget(self.japanese_text_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        self.japanese_text_scroll.setWidget(scroll_content)

    def _create_fallback_japanese_text_display(self):
        """创建备用的日语文本显示区域"""
        self.japanese_text_container = QLabel(self.character_container)
        self.japanese_text_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.japanese_text_container.setGeometry(0, 520, 438, 75)
        self.japanese_text_container.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 150);
                border-radius: 10px;
            }
        """)

        self.japanese_text_scroll = QScrollArea(self.japanese_text_container)
        self.japanese_text_scroll.setGeometry(0, 0, 438, 75)
        self.japanese_text_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.japanese_text_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.japanese_text_scroll.setWidgetResizable(True)
        self.japanese_text_scroll.setStyleSheet("""
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:vertical {
                width: 8px;
                background: transparent;
                margin: 0px 0px 0px 0px;
            }
            QScrollBar::handle:vertical {
                background: rgba(255, 255, 255, 0.5);
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: transparent;
                height: 0px;
            }
        """)

        scroll_content = QWidget()
        scroll_content.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setAlignment(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)

        self.japanese_text_label = QLabel()
        self.japanese_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.japanese_text_label.setWordWrap(True)
        self.japanese_text_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 15px;
                font-weight: bold;
                padding: 5px 8px;
                background: transparent;
            }
        """)

        scroll_layout.addWidget(self.japanese_text_label, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignCenter)
        self.japanese_text_scroll.setWidget(scroll_content)

    def load_background(self):
        """加载背景图片"""
        bg_path = IMAGES_DIR / "bg1.png"
        if bg_path.exists():
            pixmap = QPixmap(str(bg_path))
            if not pixmap.isNull():
                scaled = pixmap.scaled(438, 625, Qt.AspectRatioMode.KeepAspectRatioByExpanding, Qt.TransformationMode.SmoothTransformation)
                self.bg_label.setPixmap(scaled)
    
    def get_image_path(self):
        """获取当前表情图片路径"""
        if self.is_speaking:
            frame = (self.animation_frame % 3) + 1
        else:
            frame = 1
        image_name = f"kurisu_{self.current_emotion}{frame}.png"
        return IMAGES_DIR / image_name
    
    def update_image(self):
        """更新显示的图片"""
        try:
            image_path = self.get_image_path()
            print(f"[图片] update_image 被调用, 路径: {image_path}, 存在: {image_path.exists()}")
            if image_path.exists():
                pixmap = QPixmap(str(image_path))
                print(f"[图片] 图片已加载, 大小: {pixmap.width()}x{pixmap.height()}")
                scaled_pixmap = pixmap.scaled(
                    375, 475,
                    Qt.AspectRatioMode.KeepAspectRatio,
                    Qt.TransformationMode.SmoothTransformation
                )
                print(f"[图片] 图片已缩放, 新大小: {scaled_pixmap.width()}x{scaled_pixmap.height()}")
                self.image_label.setPixmap(scaled_pixmap)
                print(f"[图片] 图片已显示到标签")
            else:
                print(f"[图片] 图片不存在: {image_path}")
                default_path = IMAGES_DIR / f"kurisu_normal1.png"
                if default_path.exists():
                    print(f"[图片] 加载默认图片: {default_path}")
                    pixmap = QPixmap(str(default_path))
                    scaled_pixmap = pixmap.scaled(375, 475, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
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
                self.timer.start(150)
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
            try:
                self.is_speaking = False
                if hasattr(self, 'timer'):
                    self.timer.stop()
                self.update_image()
                print(f"[动画] 停止说话动画")
            except Exception as e:
                print(f"[动画] stop_speaking 异常: {e}")
    
    def next_frame(self):
        """下一帧 - 嘴部动画"""
        if self.is_speaking:
            self.animation_frame += 1
            self.update_image()
    
    def set_emotion(self, emotion: str):
        """设置表情"""
        if emotion in VALID_EMOTIONS:
            print(f"[表情] 设置表情: {emotion}")
            self.current_emotion = emotion
            self.update_image()
        else:
            print(f"[表情] 无效表情: {emotion}, 使用默认")
            self.current_emotion = "normal"
            self.update_image()
    
    def set_japanese_text(self, text: str, append: bool = False):
        """设置或追加日语文本"""
        print(f"[日语文本] set_japanese_text 被调用, 文本: {text}, 追加: {append}")
        if append:
            current_text = self.japanese_text_label.text()
            if current_text:
                text = current_text + "\n" + text
        self.japanese_text_label.setText(text)
        print(f"[日语文本] 文本已设置到标签")
        
        QTimer.singleShot(50, self._scroll_to_bottom)
    
    def _scroll_to_bottom(self):
        """滚动到底部"""
        try:
            scrollbar = self.japanese_text_scroll.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())
        except Exception as e:
            print(f"[滚动] 滚动到底部失败: {e}")
