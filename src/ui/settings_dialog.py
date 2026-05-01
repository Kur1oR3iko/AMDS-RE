"""Settings dialog for model, memory, and audio options."""

from __future__ import annotations

import requests
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from core.app_config import (
    DEFAULT_MODEL,
    DEFAULT_PRESET_AUDIO_PROBABILITY,
    DEFAULT_VOCU_ASYNC_MODE,
    DEFAULT_VOCU_FLASH_MODE,
    LEGACY_MODEL_MAP,
    MODEL_OPTIONS,
)
from core.resources import get_qsettings


class SettingsDialog(QDialog):
    """Project settings dialog."""

    def __init__(
        self,
        parent=None,
        current_api_key="",
        vocu_api_key="",
        vocu_voice_id="",
        audio_mode=True,
        current_max_tokens=500,
    ):
        super().__init__(parent)
        self._credits_requested = False
        self._geometry_finalized = False

        self.setWindowTitle("设置")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.WindowContextHelpButtonHint, False)
        self.resize(700, 760)
        self.setMinimumSize(620, 620)

        self.setStyleSheet(
            """
            QDialog { background-color: #2C1810; }
            QLabel { color: #D2691E; font-size: 14px; }
            QLineEdit, QComboBox {
                padding: 8px;
                border-radius: 5px;
                border: 2px solid #8B4513;
                background-color: white;
                color: #333333;
                min-width: 320px;
            }
            QComboBox QAbstractItemView {
                background-color: #FFFFFF;
                color: #222222;
                selection-background-color: #D2691E;
                selection-color: #FFFFFF;
                border: 1px solid #8B4513;
            }
            QPushButton {
                padding: 10px 20px;
                border-radius: 5px;
                background-color: #8B4513;
                color: white;
                font-weight: bold;
            }
            QPushButton:hover { background-color: #A0522D; }
            QCheckBox { color: #FFFFFF; font-size: 13px; spacing: 8px; }
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
            QSlider::groove:horizontal {
                height: 6px;
                background: #8B4513;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                width: 16px;
                margin: -6px 0;
                background: #D2691E;
                border-radius: 8px;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            """
        )

        qsettings = get_qsettings()
        current_model_type = qsettings.value("model_type", "默认")
        current_model = LEGACY_MODEL_MAP.get(qsettings.value("model", DEFAULT_MODEL), DEFAULT_MODEL)
        current_custom_url = qsettings.value("custom_model_url", "http://localhost:11434")
        current_custom_name = qsettings.value("custom_model_name", "")
        preset_probability = max(
            0,
            min(100, qsettings.value("preset_audio_probability", DEFAULT_PRESET_AUDIO_PROBABILITY, type=int)),
        )
        permanent_memory = qsettings.value("permanent_memory", False, type=bool)
        vocu_async_mode = qsettings.value("vocu_async_mode", DEFAULT_VOCU_ASYNC_MODE, type=bool)
        vocu_flash_mode = qsettings.value("vocu_flash_mode", DEFAULT_VOCU_FLASH_MODE, type=bool)

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(14, 14, 14, 14)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        root_layout.addWidget(scroll_area)

        content = QWidget()
        scroll_area.setWidget(content)

        layout = QVBoxLayout(content)
        layout.setSpacing(14)
        layout.setContentsMargins(18, 18, 18, 18)

        model_layout = QGridLayout()
        model_layout.setColumnStretch(1, 1)
        model_layout.setHorizontalSpacing(10)
        model_layout.setVerticalSpacing(8)

        self.model_type_combo = QComboBox()
        self.model_type_combo.addItems(["默认", "自定义"])
        self.model_type_combo.setCurrentText(current_model_type if current_model_type in ["默认", "自定义"] else "默认")
        model_layout.addWidget(QLabel("模型类型:"), 0, 0)
        model_layout.addWidget(self.model_type_combo, 0, 1)

        self.model_combo = QComboBox()
        self.model_combo.addItems(MODEL_OPTIONS)
        self.model_combo.setCurrentText(current_model if current_model in MODEL_OPTIONS else DEFAULT_MODEL)
        model_layout.addWidget(QLabel("默认模型:"), 1, 0)
        model_layout.addWidget(self.model_combo, 1, 1)

        self.custom_model_url = QLineEdit(current_custom_url)
        self.custom_model_url.setPlaceholderText("输入自定义模型 URL，例如 http://localhost:11434")
        self.custom_url_label = QLabel("自定义模型 URL:")
        model_layout.addWidget(self.custom_url_label, 2, 0)
        model_layout.addWidget(self.custom_model_url, 2, 1)

        self.custom_model_name = QLineEdit(current_custom_name)
        self.custom_model_name.setPlaceholderText("输入自定义模型名称，例如 qwen3:8b")
        self.custom_name_label = QLabel("自定义模型名称:")
        model_layout.addWidget(self.custom_name_label, 3, 0)
        model_layout.addWidget(self.custom_model_name, 3, 1)
        layout.addLayout(model_layout)

        self.api_key_label = QLabel("AI API 密钥:")
        self.api_key_input = QLineEdit(current_api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_input.setPlaceholderText("输入火山方舟 API 密钥")

        api_layout = QGridLayout()
        api_layout.setColumnStretch(1, 1)
        api_layout.addWidget(self.api_key_label, 0, 0)
        api_layout.addWidget(self.api_key_input, 0, 1)
        layout.addLayout(api_layout)

        self.max_tokens_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_tokens_slider.setMinimum(50)
        self.max_tokens_slider.setMaximum(2000)
        self.max_tokens_slider.setValue(current_max_tokens)
        self.max_tokens_label = QLabel(str(current_max_tokens))
        self.max_tokens_slider.valueChanged.connect(lambda value: self.max_tokens_label.setText(str(value)))

        tokens_row = QHBoxLayout()
        tokens_row.addWidget(QLabel("最大 Tokens 长度:"))
        tokens_row.addWidget(self.max_tokens_slider, 1)
        tokens_row.addWidget(self.max_tokens_label)
        layout.addLayout(tokens_row)

        tokens_tip = QLabel("长度越长，生成时间和音频耗点通常越高。")
        tokens_tip.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        tokens_tip.setWordWrap(True)
        layout.addWidget(tokens_tip)

        self.audio_mode_checkbox = QCheckBox("启用音频模式（生成日语音频）")
        self.audio_mode_checkbox.setChecked(audio_mode)
        layout.addWidget(self.audio_mode_checkbox)

        preset_row = QHBoxLayout()
        self.preset_probability_slider = QSlider(Qt.Orientation.Horizontal)
        self.preset_probability_slider.setMinimum(0)
        self.preset_probability_slider.setMaximum(100)
        self.preset_probability_slider.setValue(preset_probability)
        self.preset_probability_value = QLabel(f"{preset_probability}%")
        self.preset_probability_slider.valueChanged.connect(
            lambda value: self.preset_probability_value.setText(f"{value}%")
        )
        preset_row.addWidget(QLabel("预设音频概率:"))
        preset_row.addWidget(self.preset_probability_slider, 1)
        preset_row.addWidget(self.preset_probability_value)
        layout.addLayout(preset_row)

        self.permanent_memory_checkbox = QCheckBox("启用永久记忆（实验性）")
        self.permanent_memory_checkbox.setChecked(permanent_memory)
        layout.addWidget(self.permanent_memory_checkbox)

        memory_info = QLabel("开启后会保留聊天记录；关闭时会按主流程清理历史并重启。")
        memory_info.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        memory_info.setWordWrap(True)
        layout.addWidget(memory_info)

        vocu_layout = QGridLayout()
        vocu_layout.setColumnStretch(1, 1)
        vocu_layout.setHorizontalSpacing(10)
        vocu_layout.setVerticalSpacing(8)

        self.vocu_api_label = QLabel("Vocu API 密钥:")
        self.vocu_api_key_input = QLineEdit(vocu_api_key)
        self.vocu_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        self.vocu_api_key_input.setPlaceholderText("输入 Vocu API 密钥")
        vocu_layout.addWidget(self.vocu_api_label, 0, 0)
        vocu_layout.addWidget(self.vocu_api_key_input, 0, 1)

        self.vocu_voice_label = QLabel("Vocu 声音 ID:")
        self.vocu_voice_id_input = QLineEdit(vocu_voice_id)
        self.vocu_voice_id_input.setPlaceholderText("输入 Vocu 声音 ID")
        vocu_layout.addWidget(self.vocu_voice_label, 1, 0)
        vocu_layout.addWidget(self.vocu_voice_id_input, 1, 1)
        layout.addLayout(vocu_layout)

        self.vocu_async_checkbox = QCheckBox("启用 Vocu 异步生成（可能更快，但需要vocu的会员权限）")
        self.vocu_async_checkbox.setChecked(vocu_async_mode)
        layout.addWidget(self.vocu_async_checkbox)

        self.vocu_flash_checkbox = QCheckBox("启用 Vocu Flash 低延迟模式（可能更快，但音色不稳定易漂移，效果不好，建议别开）")
        self.vocu_flash_checkbox.setChecked(vocu_flash_mode)
        layout.addWidget(self.vocu_flash_checkbox)

        self.credits_label = QLabel("点数: 等待查询")
        self.credits_label.setStyleSheet("color: #FFD700; font-size: 13px;")
        layout.addWidget(self.credits_label)

        self.refresh_credits_btn = QPushButton("刷新点数")
        self.refresh_credits_btn.clicked.connect(self._fetch_credits)
        layout.addWidget(self.refresh_credits_btn)

        self.vocu_info = QLabel("特别感谢群友“过期的罐头”提供的赞助支持")
        self.vocu_info.setStyleSheet("color: #AAAAAA; font-size: 12px;")
        self.vocu_info.setWordWrap(True)
        layout.addWidget(self.vocu_info)

        github_link = QLabel(
            '项目地址：<a href="https://github.com/Kur1oR3iko/AMDS-RE">https://github.com/Kur1oR3iko/AMDS-RE</a>'
        )
        github_link.setStyleSheet("color: #4A90E2; font-size: 11px;")
        github_link.setOpenExternalLinks(True)
        layout.addWidget(github_link)

        author_info = QLabel('作者：B 站 / 抖音 "栗尾璃子Reiko"')
        author_info.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(author_info)

        group_info = QLabel("水友群：391437320 / 52680622")
        group_info.setStyleSheet("color: #888888; font-size: 12px;")
        layout.addWidget(group_info)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        self.save_button = QPushButton("保存")
        self.save_button.clicked.connect(self.accept)
        button_row.addWidget(self.save_button)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        button_row.addWidget(self.cancel_button)
        layout.addLayout(button_row)

        self.model_type_combo.currentTextChanged.connect(self._update_model_visibility)
        self.audio_mode_checkbox.stateChanged.connect(self._update_audio_visibility)
        self._update_model_visibility()
        self._update_audio_visibility()

    def _update_model_visibility(self):
        is_custom = self.model_type_combo.currentText() == "自定义"
        self.model_combo.setVisible(not is_custom)
        self.custom_url_label.setVisible(is_custom)
        self.custom_model_url.setVisible(is_custom)
        self.custom_name_label.setVisible(is_custom)
        self.custom_model_name.setVisible(is_custom)
        self.api_key_label.setVisible(not is_custom)
        self.api_key_input.setVisible(not is_custom)

    def _update_audio_visibility(self):
        is_audio_enabled = self.audio_mode_checkbox.isChecked()
        for widget in (
            self.vocu_api_label,
            self.vocu_api_key_input,
            self.vocu_voice_label,
            self.vocu_voice_id_input,
            self.vocu_async_checkbox,
            self.vocu_flash_checkbox,
            self.credits_label,
            self.refresh_credits_btn,
            self.vocu_info,
        ):
            widget.setVisible(is_audio_enabled)

    def showEvent(self, event):
        super().showEvent(event)
        if not self._geometry_finalized:
            self._geometry_finalized = True
            QTimer.singleShot(0, self._finalize_initial_layout)
        if not self._credits_requested:
            self._credits_requested = True
            QTimer.singleShot(200, self._fetch_credits)

    def _finalize_initial_layout(self):
        self.ensurePolished()
        if self.layout():
            self.layout().activate()
        hinted = self.sizeHint()
        self.resize(max(700, hinted.width()), max(680, hinted.height()))
        self._reposition_dialog()
        self.updateGeometry()

    def _reposition_dialog(self):
        screen = None
        if self.windowHandle() and self.windowHandle().screen():
            screen = self.windowHandle().screen()
        elif self.parentWidget() and self.parentWidget().windowHandle() and self.parentWidget().windowHandle().screen():
            screen = self.parentWidget().windowHandle().screen()
        else:
            screen = QGuiApplication.primaryScreen()

        if not screen:
            return

        available = screen.availableGeometry()
        margin = 24
        width = min(max(self.width(), 620), max(420, available.width() - margin * 2))
        height = min(max(self.height(), 620), max(420, available.height() - margin * 2))
        self.resize(width, height)
        x = available.x() + max(margin, (available.width() - width) // 2)
        y = available.y() + max(margin, (available.height() - height) // 2)
        self.move(x, y)

    def _fetch_credits(self):
        api_key = self.vocu_api_key_input.text().strip()
        if not api_key:
            self.credits_label.setText("点数: 请先输入 Vocu API 密钥")
            self.credits_label.setStyleSheet("color: #FFD700; font-size: 13px;")
            return

        try:
            response = requests.get(
                "https://v1.vocu.studio/api/account/info",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10,
                verify=False,
            )
            data = response.json()
            if data.get("status") == 200:
                credits = data.get("user", {}).get("credits", 0)
                self.credits_label.setText(f"点数: {credits}")
                self.credits_label.setStyleSheet("color: #00FF88; font-size: 13px;")
            else:
                self.credits_label.setText("点数: 查询失败")
                self.credits_label.setStyleSheet("color: #FF6347; font-size: 13px;")
        except Exception:
            self.credits_label.setText("点数: 查询失败")
            self.credits_label.setStyleSheet("color: #FF6347; font-size: 13px;")

    def get_settings(self):
        return {
            "api_key": self.api_key_input.text().strip(),
            "model_type": self.model_type_combo.currentText(),
            "model": self.model_combo.currentText(),
            "custom_model_url": self.custom_model_url.text().strip(),
            "custom_model_name": self.custom_model_name.text().strip(),
            "vocu_api_key": self.vocu_api_key_input.text().strip(),
            "vocu_voice_id": self.vocu_voice_id_input.text().strip(),
            "audio_mode": self.audio_mode_checkbox.isChecked(),
            "vocu_async_mode": self.vocu_async_checkbox.isChecked(),
            "vocu_flash_mode": self.vocu_flash_checkbox.isChecked(),
            "preset_audio_probability": self.preset_probability_slider.value(),
            "permanent_memory": self.permanent_memory_checkbox.isChecked(),
            "max_tokens": self.max_tokens_slider.value(),
        }
