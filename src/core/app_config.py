"""
全局应用配置常量
定义模型列表、默认参数等，供其他模块统一引用
"""

# 默认使用的豆包模型（火山方舟平台）
DEFAULT_MODEL = "doubao-seed-2-0-mini-260215"

# 用户可在设置界面选择的模型列表
MODEL_OPTIONS = [
    "doubao-seed-2-0-mini-260215",
    "doubao-seed-2-0-lite-260215",
    "doubao-seed-2-0-pro-260215",
    "doubao-seed-1-8-251228",
]

# 旧版模型名到新版模型名的映射，用于自动迁移旧配置
LEGACY_MODEL_MAP = {
    "doubao-seed-1-6-lite-251015": DEFAULT_MODEL,
}

# 预设音频触发概率（百分比），即用户输入匹配到预设关键词时使用预设音频而非AI生成的概率
DEFAULT_PRESET_AUDIO_PROBABILITY = 30

# Vocu 异步生成模式默认关闭（通常需要付费会员才能使用）
DEFAULT_VOCU_ASYNC_MODE = False

# Vocu flash 低延迟模式默认关闭：可能更快，但音色稳定性可能下降
DEFAULT_VOCU_FLASH_MODE = False
