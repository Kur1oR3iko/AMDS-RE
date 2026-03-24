"""
音频播放模块
"""
from PyQt6.QtCore import QThread, pyqtSignal


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
            self.started.emit()
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                self.msleep(100)
        except Exception as e:
            print(f"音频播放错误: {e}")
        self.finished.emit()
