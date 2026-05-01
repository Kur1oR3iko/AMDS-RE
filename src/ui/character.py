"""Kurisu character display widget."""

from __future__ import annotations

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QLabel, QScrollArea, QVBoxLayout, QWidget

from core.resources import IMAGES_DIR


class KurisuCharacter(QWidget):
    """Character display with background, portrait animation, and Japanese subtitle area."""

    _pixmap_cache: dict[tuple[str, int, int, str], QPixmap] = {}

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.current_emotion = "normal"
        self.animation_frame = 0
        self.is_speaking = False
        self.timer: QTimer | None = None
        self.setup_ui()
        self.update_image()

    def setup_ui(self):
        """Build the layered portrait UI."""
        self.setStyleSheet("background: transparent;")

        self.main_layout = QVBoxLayout(self)
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.character_container = QWidget()
        self.character_container.setMinimumSize(438, 625)
        self.character_container.setMaximumSize(438, 625)
        self.character_container.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.character_container.setStyleSheet("background: transparent;")

        self.bg_label = QLabel(self.character_container)
        self.bg_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.bg_label.setGeometry(0, 0, 438, 625)
        self.bg_label.setStyleSheet("background: transparent;")
        self.load_background()

        self.image_label = QLabel(self.character_container)
        self.image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image_label.setGeometry(32, 63, 375, 500)
        self.image_label.setStyleSheet("background: transparent;")

        self._setup_subtitle_area()
        self.main_layout.addWidget(self.character_container, alignment=Qt.AlignmentFlag.AlignCenter)

    def _setup_subtitle_area(self):
        """Create the Japanese subtitle frame and scrollable text area."""
        subtitle_frame_path = IMAGES_DIR / "subtitle_frame_big.png"

        self.japanese_text_container = QLabel(self.character_container)
        self.japanese_text_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.japanese_text_container.setGeometry(0, 563, 438, 62)

        if subtitle_frame_path.exists():
            pixmap = QPixmap(str(subtitle_frame_path))
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(
                    438,
                    62,
                    Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                    Qt.TransformationMode.SmoothTransformation,
                )
                self.japanese_text_container.setPixmap(scaled_pixmap)
            else:
                self.japanese_text_container.setStyleSheet(
                    "background-color: rgba(0, 0, 0, 150); border-radius: 10px;"
                )
        else:
            self.japanese_text_container.setStyleSheet(
                "background-color: rgba(0, 0, 0, 150); border-radius: 10px;"
            )

        self.japanese_text_scroll = QScrollArea(self.japanese_text_container)
        self.japanese_text_scroll.setGeometry(0, 0, 438, 62)
        self.japanese_text_scroll.setWidgetResizable(True)
        self.japanese_text_scroll.setStyleSheet(
            """
            QScrollArea {
                background: transparent;
                border: none;
            }
            QScrollBar:horizontal {
                height: 8px;
                background: transparent;
                margin: 0;
            }
            QScrollBar::handle:horizontal {
                background: rgba(255, 255, 255, 0.5);
                min-width: 20px;
                border-radius: 4px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                background: transparent;
                width: 0;
            }
            """
        )

        self.japanese_text_label = QLabel()
        self.japanese_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.japanese_text_label.setWordWrap(True)
        self.japanese_text_label.setStyleSheet(
            """
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px;
                background: transparent;
            }
            """
        )
        self.japanese_text_label.setText("")
        self.japanese_text_scroll.setWidget(self.japanese_text_label)

    def load_background(self):
        """Load the portrait background image."""
        bg_path = IMAGES_DIR / "bg1.png"
        if bg_path.exists():
            scaled = self._get_scaled_pixmap(
                bg_path,
                438,
                625,
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            )
            if scaled is not None:
                self.bg_label.setPixmap(scaled)

    def get_image_path(self):
        """Return the current portrait image path."""
        frame = (self.animation_frame % 3) + 1 if self.is_speaking else 1
        image_name = f"kurisu_{self.current_emotion}{frame}.png"
        return IMAGES_DIR / image_name

    def update_image(self):
        """Refresh the portrait image."""
        try:
            image_path = self.get_image_path()
            if image_path.exists():
                scaled_pixmap = self._get_scaled_pixmap(
                    image_path,
                    375,
                    500,
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
                if scaled_pixmap is not None:
                    self.image_label.setPixmap(scaled_pixmap)
                return

            print(f"[图片] 角色图片不存在: {image_path}")
            default_path = IMAGES_DIR / "kurisu_normal1.png"
            if default_path.exists():
                scaled_pixmap = self._get_scaled_pixmap(
                    default_path,
                    375,
                    500,
                    Qt.AspectRatioMode.KeepAspectRatio,
                )
                if scaled_pixmap is not None:
                    self.image_label.setPixmap(scaled_pixmap)
        except Exception as exc:
            print(f"[图片] 更新角色图片失败: {exc}")

    @classmethod
    def _get_scaled_pixmap(cls, image_path, width: int, height: int, aspect_mode):
        """Load and cache scaled pixmaps."""
        cache_key = (str(image_path), width, height, str(aspect_mode))
        if cache_key in cls._pixmap_cache:
            return cls._pixmap_cache[cache_key]

        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return None

        scaled = pixmap.scaled(
            width,
            height,
            aspect_mode,
            Qt.TransformationMode.SmoothTransformation,
        )
        cls._pixmap_cache[cache_key] = scaled
        return scaled

    def start_speaking(self):
        """Start mouth animation."""
        print(f"[动画] start_speaking 被调用, 当前状态: {self.is_speaking}")
        if self.is_speaking:
            return

        self.is_speaking = True
        self.animation_frame = 0
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.timer.start(150)
        print("[动画] 定时器已启动，间隔150ms")
        self.update_image()
        print(f"[动画] 开始说话动画，当前表情: {self.current_emotion}, 帧: {self.animation_frame}")

    def stop_speaking(self):
        """Stop mouth animation."""
        if not self.is_speaking:
            return

        self.is_speaking = False
        if self.timer is not None:
            self.timer.stop()
        self.animation_frame = 0
        self.update_image()

    def next_frame(self):
        """Advance to the next mouth frame."""
        try:
            self.animation_frame = (self.animation_frame + 1) % 3
            self.update_image()
        except Exception as exc:
            print(f"[动画] 切换下一帧失败: {exc}")

    def set_emotion(self, emotion: str):
        """Set the current character emotion."""
        valid_emotions = [
            "normal",
            "happy",
            "angry",
            "sad",
            "blush",
            "annoyed",
            "disappointed",
            "eyes_closed",
            "indifferent",
            "pissed",
            "side",
            "sided_angry",
            "sided_blush",
            "sided_eyes_closed",
            "sided_pleasant",
            "sided_surprised",
            "sided_thinking",
            "sided_worried",
            "winking",
        ]
        if emotion not in valid_emotions:
            print(f"[表情] 无效表情: {emotion}，回退为 normal")
            emotion = "normal"

        self.current_emotion = emotion
        print(f"[表情] 设置表情为: {emotion}")
        self.update_image()

    def set_japanese_text(self, text: str):
        """Update the subtitle text shown under the portrait."""
        print(f"[日语文本] set_japanese_text 被调用, 文本: {text}")
        self.japanese_text_label.setText(text)
        print("[日语文本] 文本已设置到标签")
