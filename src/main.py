"""AMDS desktop application entry point."""

from __future__ import annotations

import os
import sys
import traceback

from PyQt6.QtCore import QTimer
from PyQt6.QtWidgets import QApplication, QMessageBox

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ui.main_window import MainWindow
from ui.splash_screen import SplashScreen
from utils.debug_log import install_debug_logging


def main():
    install_debug_logging()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    splash = SplashScreen()
    splash.show()

    window = MainWindow()

    state = {
        "resources_ready": False,
        "animation_ready": False,
        "shown": False,
    }

    def try_show_main_window():
        if state["shown"] or not (state["resources_ready"] and state["animation_ready"]):
            return
        state["shown"] = True
        window.show()
        app.processEvents()
        splash.stop_animation()
        splash.close()
        window.play_tone()

    def init_resources():
        try:
            print("[启动] 开始初始化资源...")
            window.chat.init_resources()
            print("[启动] 资源初始化完成")
            state["resources_ready"] = True
            try_show_main_window()
        except Exception as exc:
            print(f"[启动] 资源初始化失败: {exc}")
            traceback.print_exc()
            splash.stop_animation()
            splash.close()
            QMessageBox.critical(
                None,
                "AMDS 启动失败",
                "程序在启动阶段发生异常，已停止在启动动画页面。\n"
                "可查看 `%LOCALAPPDATA%\\AMDS\\runtime.log` 获取详细日志。",
            )
            app.quit()

    def on_animation_ready():
        state["animation_ready"] = True
        try_show_main_window()

    splash.first_cycle_finished.connect(on_animation_ready)
    QTimer.singleShot(0, init_resources)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
