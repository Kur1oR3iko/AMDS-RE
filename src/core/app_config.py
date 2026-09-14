"""
全局应用配置常量
定义模型列表、默认参数等，供其他模块统一引用
"""

# 默认使用的豆包模型（火山方舟平台）
DEFAULT_MODEL = "doubao-seed-2-0-mini-260215"

# Deepseek OpenAI 兼容接口配置
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEFAULT_DEEPSEEK_MODEL = "deepseek-v4-flash"
DEEPSEEK_MODEL_OPTIONS = [
    "deepseek-v4-flash",
    "deepseek-v4-pro",
]

# OpenAI Responses API 兼容端点（密钥只从本地设置读取，不写入源码）
RESPONSES_PROVIDER_TYPE = "Responses API"
DEFAULT_RESPONSES_BASE_URL = "https://newapi.caner.hk/v1"
DEFAULT_RESPONSES_MODEL = "gpt-5.6-luna"

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

# 优先调用 Vocu simple-generate 的 streamUrl，失败再回退到任务接口
DEFAULT_VOCU_REALTIME_MODE = True

# Vocu flash 低延迟模式默认关闭：可能更快，但音色稳定性可能下降
DEFAULT_VOCU_FLASH_MODE = False

# 记忆系统：近期原文 + 滚动摘要，避免永久记忆时无限扩张上下文
DEFAULT_RECENT_MEMORY_MESSAGES = 24
DEFAULT_CONTEXT_MAX_CHARS = 24000
DEFAULT_MEMORY_SUMMARY_TRIGGER = 36
DEFAULT_MEMORY_KEEP_RECENT = 20
