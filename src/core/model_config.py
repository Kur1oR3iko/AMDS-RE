"""读取本地 ``模型.txt`` 的一次性开发配置。

该文件包含密钥，已加入 .gitignore，不会被 PyInstaller 打包。
发行版仍通过设置窗口配置密钥。
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

from core.app_config import RESPONSES_PROVIDER_TYPE


@dataclass(frozen=True)
class LocalModelConfig:
    chat_base_url: str = ""
    chat_api_key: str = ""
    chat_model: str = ""
    vocu_api_key: str = ""
    vocu_voice_id: str = ""
    fingerprint: str = ""

    @property
    def is_complete(self) -> bool:
        return bool(self.chat_base_url and self.chat_api_key and self.chat_model)


def _candidate_paths() -> list[Path]:
    paths = [Path(__file__).resolve().parents[2] / "模型.txt"]
    if getattr(sys, "frozen", False):
        paths.insert(0, Path(sys.executable).resolve().parent / "模型.txt")
    return paths


def load_local_model_config() -> LocalModelConfig:
    """解析用户提供的简易配置：前三项是对话端点，后两项是 Vocu。"""
    path = next((candidate for candidate in _candidate_paths() if candidate.is_file()), None)
    if path is None:
        return LocalModelConfig()

    try:
        raw = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return LocalModelConfig()

    values: dict[str, list[str]] = {"链接": [], "文档": [], "密钥": [], "模型": []}
    for line in raw.splitlines():
        match = re.match(r"^\s*(链接|文档|密钥|模型)\s*[:：]?\s*(.*?)\s*$", line)
        if match and match.group(2):
            values[match.group(1)].append(match.group(2))

    keys = values["密钥"]
    models = values["模型"]
    links = values["链接"]
    return LocalModelConfig(
        chat_base_url=links[0].rstrip("/") if links else "",
        chat_api_key=keys[0] if keys else "",
        chat_model=models[0] if models else "",
        vocu_api_key=keys[1] if len(keys) > 1 else "",
        vocu_voice_id=models[1] if len(models) > 1 else "",
        fingerprint=hashlib.sha256(raw.encode("utf-8")).hexdigest(),
    )


def import_local_model_settings(qsettings) -> bool:
    """将新的本地配置安全导入 QSettings；同一版本只导入一次。"""
    config = load_local_model_config()
    if not config.is_complete or qsettings.value("model_file_fingerprint", "") == config.fingerprint:
        return False

    qsettings.setValue("responses_base_url", config.chat_base_url)
    qsettings.setValue("responses_api_key", config.chat_api_key)
    qsettings.setValue("responses_model", config.chat_model)
    qsettings.setValue("model_type", RESPONSES_PROVIDER_TYPE)
    if config.vocu_api_key:
        qsettings.setValue("vocu_api_key", config.vocu_api_key)
    if config.vocu_voice_id:
        qsettings.setValue("vocu_voice_id", config.vocu_voice_id)
        qsettings.setValue("audio_mode", True)
        qsettings.setValue("vocu_realtime_mode", True)
    qsettings.setValue("model_file_fingerprint", config.fingerprint)
    qsettings.sync()
    return True
