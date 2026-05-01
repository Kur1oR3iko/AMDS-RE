"""Startup splash animation."""

from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QVBoxLayout, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPixmap

from core.resources import IMAGES_DIR

class SplashScreen(QMainWindow):
    """启动动画窗口 - 使用Logo序列"""
    first_cycle_finished = pyqtSignal()
    _logo_cache = {}
    
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
        version = QLabel("v0.3.0")
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
        self.animation_speed = 64  # ms per frame, 20% faster than 80ms
        self._first_cycle_finished = False
        
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
            cache_key = str(logo_path)
            scaled = self._logo_cache.get(cache_key)
            if scaled is None:
                pixmap = QPixmap(cache_key)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(180, 180, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
                    self._logo_cache[cache_key] = scaled
            if scaled is not None:
                self.logo_label.setPixmap(scaled)
        
        self.current_frame += 1
        if self.current_frame > self.total_frames:
            self.current_frame = 1  # 循环播放
            if not self._first_cycle_finished:
                self._first_cycle_finished = True
                self.first_cycle_finished.emit()
    
    def stop_animation(self):
        """停止动画"""
        if hasattr(self, 'timer'):
            self.timer.stop()
