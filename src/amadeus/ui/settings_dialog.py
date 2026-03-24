"""
设置对话框
"""
import requests

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QLineEdit, QPushButton,
    QHBoxLayout, QComboBox, QCheckBox, QGridLayout, QSlider, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt, QTimer


class SettingsDialog(QDialog):
    """设置对话框"""
    
    def __init__(self, parent=None, current_api_key="", vocu_api_key="",
                 vocu_voice_id="", audio_mode=True, max_tokens=500,
                 current_model="doubao-seed-2-0-lite-260215",
                 current_model_type="默认",
                 current_custom_url="http://localhost:11434",
                 current_custom_name="",
                 preset_probability=30, async_audio_generation=False):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setMinimumWidth(500)
        self.setStyleSheet("""
            QDialog {
                background-color: #2C1810;
            }
            QLabel {
                color: #FFFFFF;
            }
            QLineEdit {
                padding: 8px;
                border-radius: 5px;
                border: 1px solid #8B4513;
                background-color: #3C2820;
                color: #FFFFFF;
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
            QComboBox {
                padding: 8px;
                border-radius: 5px;
                border: 1px solid #8B4513;
                background-color: #3C2820;
                color: #FFFFFF;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 5px solid #FFFFFF;
                margin-right: 10px;
            }
            QSlider::groove:horizontal {
                border: 1px solid #8B4513;
                height: 8px;
                background: #3C2820;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #D2691E;
                border: 1px solid #8B4513;
                width: 18px;
                margin: -5px 0;
                border-radius: 9px;
            }
        """)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                border: none;
                background: transparent;
            }
            QScrollArea > QWidget > QWidget {
                background: transparent;
            }
            QScrollBar:vertical {
                background: #3C2820;
                width: 12px;
                border: none;
                border-radius: 6px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background: #8B4513;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background: #D2691E;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: none;
            }
        """)

        scroll_content = QWidget()
        scroll_content.setStyleSheet("background: transparent;")
        layout = QVBoxLayout(scroll_content)
        layout.setSpacing(15)

        title = QLabel("系统设置")
        title.setStyleSheet("color: #D2691E; font-size: 20px; font-weight: bold;")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        model_layout = QGridLayout()
        model_layout.setColumnStretch(1, 1)
        model_layout.setHorizontalSpacing(10)
        model_layout.setVerticalSpacing(8)
        
        model_type_label = QLabel("模型类型:")
        model_type_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        model_type_label.setMinimumWidth(100)
        model_type_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.model_type_combo = QComboBox()
        self.model_type_combo.addItems(["默认", "自定义"])
        model_layout.addWidget(model_type_label, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model_layout.addWidget(self.model_type_combo, 0, 1)
        
        default_model_label = QLabel("默认模型:")
        default_model_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        default_model_label.setMinimumWidth(100)
        default_model_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.model_combo = QComboBox()
        model_options = [
            "doubao-seed-2-0-pro-260215",
            "doubao-seed-2-0-lite-260215",
            "doubao-seed-2-0-mini-260215",
            "doubao-seed-1-8-251228",
        ]
        self.model_combo.addItems(model_options)
        model_layout.addWidget(default_model_label, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model_layout.addWidget(self.model_combo, 1, 1)
        
        custom_url_label = QLabel("自定义URL:")
        custom_url_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        custom_url_label.setMinimumWidth(100)
        custom_url_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.custom_model_url = QLineEdit()
        self.custom_model_url.setPlaceholderText("http://localhost:11434")
        model_layout.addWidget(custom_url_label, 2, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model_layout.addWidget(self.custom_model_url, 2, 1)
        
        custom_name_label = QLabel("模型名称:")
        custom_name_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        custom_name_label.setMinimumWidth(100)
        custom_name_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.custom_model_name = QLineEdit()
        self.custom_model_name.setPlaceholderText("例如: llama2, mistral")
        model_layout.addWidget(custom_name_label, 3, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model_layout.addWidget(self.custom_model_name, 3, 1)
        
        if current_model_type:
            self.model_type_combo.setCurrentText(current_model_type)
        if current_model in model_options:
            self.model_combo.setCurrentText(current_model)
        self.custom_model_url.setText(current_custom_url)
        self.custom_model_name.setText(current_custom_name)
        
        api_tokens_layout = QGridLayout()
        api_tokens_layout.setColumnStretch(1, 1)
        api_tokens_layout.setHorizontalSpacing(10)
        api_tokens_layout.setVerticalSpacing(8)
        
        api_key_label = QLabel("AI API密钥:")
        api_key_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        api_key_label.setMinimumWidth(100)
        api_key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("输入火山方舟API密钥...")
        self.api_key_input.setText(current_api_key)
        self.api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        api_tokens_layout.addWidget(api_key_label, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        api_tokens_layout.addWidget(self.api_key_input, 0, 1)
        
        def update_model_visibility():
            is_custom = self.model_type_combo.currentText() == "自定义"
            default_model_label.setVisible(not is_custom)
            self.model_combo.setVisible(not is_custom)
            custom_url_label.setVisible(is_custom)
            self.custom_model_url.setVisible(is_custom)
            custom_name_label.setVisible(is_custom)
            self.custom_model_name.setVisible(is_custom)
            api_key_label.setVisible(not is_custom)
            self.api_key_input.setVisible(not is_custom)
        
        self.model_type_combo.currentTextChanged.connect(update_model_visibility)
        update_model_visibility()
        
        layout.addLayout(model_layout)
        
        line = QLabel("─" * 40)
        line.setStyleSheet("color: #8B4513;")
        line.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(line)
        
        layout.addLayout(api_tokens_layout)
        
        tokens_label = QLabel("最大Tokens长度:")
        tokens_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        tokens_label.setMinimumWidth(100)
        self.max_tokens_slider = QSlider(Qt.Orientation.Horizontal)
        self.max_tokens_slider.setMinimum(50)
        self.max_tokens_slider.setMaximum(2000)
        self.max_tokens_slider.setValue(max_tokens)
        self.max_tokens_slider.setTickInterval(100)
        self.max_tokens_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.max_tokens_slider.setMinimumWidth(250)
        
        self.max_tokens_label = QLabel(f"{max_tokens}")
        self.max_tokens_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.max_tokens_label.setFixedWidth(50)
        
        self.max_tokens_slider.valueChanged.connect(lambda value: self.max_tokens_label.setText(f"{value}"))
        
        tokens_control_layout = QHBoxLayout()
        tokens_control_layout.addWidget(self.max_tokens_slider)
        tokens_control_layout.addWidget(self.max_tokens_label)
        
        tokens_row_widget = QWidget()
        tokens_row_layout = QHBoxLayout(tokens_row_widget)
        tokens_row_layout.setContentsMargins(0, 0, 0, 0)
        tokens_row_layout.addWidget(tokens_label)
        tokens_row_layout.addLayout(tokens_control_layout)
        
        layout.addWidget(tokens_row_widget)
        
        tokens_tip = QLabel('长度越长，生成时间越长，音频处理消耗点数越多。\n注意：50个tokens实际可能只有25-40个中文字符输出')
        tokens_tip.setStyleSheet('color: #888; font-size: 12px;')
        tokens_tip.setWordWrap(True)
        layout.addWidget(tokens_tip)
        
        self.permanent_memory_checkbox = QCheckBox("启用永久记忆（实验性）")
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
        
        memory_info = QLabel("开启后将永久保存对话历史，关闭软件后再打开仍能保持记忆。关闭此选项会清除所有历史记录并重启软件。（实际仍受限于上下文窗口，但256k的极限应该一时半会不会用完）")
        memory_info.setStyleSheet("color: #888; font-size: 11px;")
        memory_info.setWordWrap(True)
        layout.addWidget(memory_info)
        
        line2 = QLabel("─" * 40)
        line2.setStyleSheet("color: #8B4513;")
        line2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(line2)
        
        self.audio_mode_checkbox = QCheckBox("启用音频模式（生成日语音频）")
        self.audio_mode_checkbox.setChecked(audio_mode)
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
        
        preset_prob_label = QLabel("预设音频概率:")
        preset_prob_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        preset_prob_label.setMinimumWidth(100)
        
        self.preset_prob_slider = QSlider(Qt.Orientation.Horizontal)
        self.preset_prob_slider.setMinimum(0)
        self.preset_prob_slider.setMaximum(100)
        self.preset_prob_slider.setSingleStep(10)
        self.preset_prob_slider.setValue(preset_probability)
        self.preset_prob_slider.setMinimumWidth(250)
        
        self.preset_prob_value = QLabel(f"{preset_probability}%")
        self.preset_prob_value.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preset_prob_value.setFixedWidth(50)
        self.preset_prob_value.setStyleSheet("color: #FFFFFF; font-size: 13px;")
        
        self.preset_prob_slider.valueChanged.connect(
            lambda value: self.preset_prob_value.setText(f"{value}%")
        )
        
        preset_prob_control_layout = QHBoxLayout()
        preset_prob_control_layout.addWidget(self.preset_prob_slider)
        preset_prob_control_layout.addWidget(self.preset_prob_value)
        
        preset_prob_row_widget = QWidget()
        preset_prob_row_layout = QHBoxLayout(preset_prob_row_widget)
        preset_prob_row_layout.setContentsMargins(0, 0, 0, 0)
        preset_prob_row_layout.addWidget(preset_prob_label)
        preset_prob_row_layout.addLayout(preset_prob_control_layout)
        
        layout.addWidget(preset_prob_row_widget)
        
        preset_prob_tip = QLabel("设置预设音频出现的概率，0%表示完全由AI生成回复")
        preset_prob_tip.setStyleSheet("color: #888; font-size: 11px;")
        preset_prob_tip.setWordWrap(True)
        layout.addWidget(preset_prob_tip)

        audio_gen_layout = QHBoxLayout()
        self.async_audio_checkbox = QCheckBox("启用异步音频生成（付费，延迟更低）")
        self.async_audio_checkbox.setChecked(async_audio_generation)
        self.async_audio_checkbox.setStyleSheet("""
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
        audio_gen_layout.addWidget(self.async_audio_checkbox)
        layout.addLayout(audio_gen_layout)

        audio_gen_info = QLabel("关闭=同步生成（免费，可能有延迟）| 开启=异步生成（付费，延迟更低）")
        audio_gen_info.setStyleSheet("color: #888; font-size: 11px;")
        audio_gen_info.setWordWrap(True)
        layout.addWidget(audio_gen_info)

        vocu_layout = QGridLayout()
        vocu_layout.setColumnStretch(1, 1)
        vocu_layout.setHorizontalSpacing(10)
        vocu_layout.setVerticalSpacing(8)
        
        vocu_api_label = QLabel("Vocu API密钥:")
        vocu_api_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        vocu_api_label.setMinimumWidth(100)
        vocu_api_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.vocu_api_key_input = QLineEdit()
        self.vocu_api_key_input.setPlaceholderText("输入Vocu API密钥（可选，用于日语音频生成）...")
        self.vocu_api_key_input.setText(vocu_api_key)
        self.vocu_api_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        vocu_layout.addWidget(vocu_api_label, 0, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vocu_layout.addWidget(self.vocu_api_key_input, 0, 1)
        
        vocu_voice_label = QLabel("Vocu声音ID:")
        vocu_voice_label.setStyleSheet("color: #D2691E; font-size: 14px;")
        vocu_voice_label.setMinimumWidth(100)
        vocu_voice_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.vocu_voice_id_input = QLineEdit()
        self.vocu_voice_id_input.setPlaceholderText("输入Vocu声音ID（用于日语音频生成）...")
        self.vocu_voice_id_input.setText(vocu_voice_id)
        vocu_layout.addWidget(vocu_voice_label, 1, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        vocu_layout.addWidget(self.vocu_voice_id_input, 1, 1)
        
        self.credits_label = QLabel("点数: 查询中...")
        self.credits_label.setStyleSheet("color: #FFD700; font-size: 13px;")
        
        self.refresh_credits_btn = QPushButton("刷新点数")
        self.refresh_credits_btn.setStyleSheet("""
            QPushButton {
                padding: 8px 16px;
                border-radius: 5px;
                background-color: #8B4513;
                color: white;
                font-weight: bold;
                border: 1px solid #6B3410;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
        """)
        self.refresh_credits_btn.clicked.connect(self._fetch_credits)
        
        self.vocu_info = QLabel("配置后可生成牧濑红莉栖的日语音频")
        self.vocu_info.setStyleSheet("color: #888; font-size: 11px;")
        
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
        
        layout.addLayout(vocu_layout)
        layout.addWidget(self.credits_label)
        layout.addWidget(self.refresh_credits_btn)
        layout.addWidget(self.vocu_info)

        github_link = QLabel('项目地址：<a href="https://github.com/Kur1oR3iko/AMDS-RE">https://github.com/Kur1oR3iko/AMDS-RE</a>')
        github_link.setStyleSheet("color: #4A90E2; font-size: 11px;")
        github_link.setOpenExternalLinks(True)
        layout.addWidget(github_link)
        
        author_info = QLabel('b站/抖音"栗尾玲子Reiko"最新力作')
        author_info.setStyleSheet("color: #888; font-size: 12px; margin-top: 8px;")
        author_info.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(author_info)
        
        thanks_info = QLabel('特别鸣谢"过期的罐头"的赞助支持和api调用帮助以促进Amadeus RE开发')
        thanks_info.setStyleSheet("color: #FFD700; font-size: 11px; margin-top: 2px;")
        thanks_info.setAlignment(Qt.AlignmentFlag.AlignLeft)
        thanks_info.setWordWrap(True)
        layout.addWidget(thanks_info)
        
        group_info = QLabel('水友群1:391437320，2群852680622')
        group_info.setStyleSheet("color: #888; font-size: 12px; margin-top: 2px;")
        group_info.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(group_info)

        button_layout = QHBoxLayout()
        button_layout.addStretch()

        button_style = """
            QPushButton {
                padding: 10px 20px;
                border-radius: 5px;
                background-color: #8B4513;
                color: white;
                font-weight: bold;
                border: 1px solid #6B3410;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #A0522D;
            }
        """

        self.save_button = QPushButton("保存")
        self.save_button.setStyleSheet(button_style)
        self.save_button.clicked.connect(self.accept)
        button_layout.addWidget(self.save_button)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setStyleSheet(button_style)
        self.cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_button)

        layout.addLayout(button_layout)

        scroll_area.setWidget(scroll_content)
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(scroll_area)

        self.setMinimumHeight(600)
        self.setMaximumHeight(700)

        def adjust_dialog_size():
            default_model_label.setVisible(False)
            self.model_combo.setVisible(False)
            custom_url_label.setVisible(False)
            self.custom_model_url.setVisible(False)
            custom_name_label.setVisible(False)
            self.custom_model_name.setVisible(False)
            api_key_label.setVisible(False)
            self.api_key_input.setVisible(False)
            
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
            
            self.adjustSize()
        
        self.model_type_combo.currentTextChanged.connect(adjust_dialog_size)
        self.audio_mode_checkbox.stateChanged.connect(adjust_dialog_size)

        QTimer.singleShot(100, self._fetch_credits)

    def _fetch_credits(self):
        """获取Vocu账户点数"""
        vocu_api_key = self.vocu_api_key_input.text().strip()
        if not vocu_api_key:
            self.credits_label.setText("点数: 请先输入API密钥")
            return

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
            "max_tokens": self.max_tokens_slider.value(),
            "preset_probability": self.preset_prob_slider.value(),
            "async_audio_generation": self.async_audio_checkbox.isChecked()
        }
