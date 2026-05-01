"""Debug widgets for viewing runtime logs from inside the packaged app."""

import os
import sys
import threading

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QTextCursor
from PyQt6.QtWidgets import QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget

from core.resources import get_config_dir
from utils.debug_log import runtime_log


class DebugTitleLabel(QLabel):
    triple_clicked = pyqtSignal()

    def __init__(self, text: str, parent=None):
        super().__init__(text, parent)
        self._click_count = 0
        self._reset_timer = QTimer(self)
        self._reset_timer.setSingleShot(True)
        self._reset_timer.timeout.connect(self._reset_clicks)

    def mousePressEvent(self, event):
        self._click_count += 1
        self._reset_timer.start(900)
        if self._click_count >= 3:
            self._reset_clicks()
            self.triple_clicked.emit()
        super().mousePressEvent(event)

    def _reset_clicks(self):
        self._click_count = 0


class DebugWindow(QWidget):
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(None)
        self.setWindowFlag(Qt.WindowType.Window, True)
        self.setWindowTitle("Amadeus Debug")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        self.status_label = QLabel()
        self.log_view = QTextEdit()
        self.log_view.setReadOnly(True)
        self._follow_logs = True

        button_layout = QHBoxLayout()
        refresh_button = QPushButton("刷新")
        refresh_button.clicked.connect(self.refresh)
        close_button = QPushButton("关闭")
        close_button.clicked.connect(self.close)
        button_layout.addWidget(refresh_button)
        button_layout.addWidget(close_button)

        layout.addWidget(self.status_label)
        layout.addWidget(self.log_view, 1)
        layout.addLayout(button_layout)

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh)
        self.refresh_timer.start(1000)
        self.log_view.verticalScrollBar().valueChanged.connect(self._on_scroll_changed)
        self.refresh()

    def refresh(self):
        self.status_label.setText(
            " | ".join([
                f"Python: {sys.version.split()[0]}",
                f"PID: {os.getpid()}",
                f"Threads: {threading.active_count()}",
                f"Config: {get_config_dir()}",
            ])
        )
        scrollbar = self.log_view.verticalScrollBar()
        was_near_bottom = scrollbar.value() >= max(0, scrollbar.maximum() - 4)
        self.log_view.setPlainText(runtime_log.text())
        if self._follow_logs or was_near_bottom:
            self.log_view.moveCursor(QTextCursor.MoveOperation.End)
            self._follow_logs = True

    def _on_scroll_changed(self, value: int):
        scrollbar = self.log_view.verticalScrollBar()
        self._follow_logs = value >= max(0, scrollbar.maximum() - 4)

    def closeEvent(self, event):
        self.refresh_timer.stop()
        self.closed.emit()
        super().closeEvent(event)
