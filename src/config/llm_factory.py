"""
LLM Factory

统一的 LLM 实例创建模块。
支持 aliyun, anthropic, openai, openrouter 四种 provider。

该模块整合了之前分散在多处的 LLM 创建逻辑：
- src/agent/research_agent.py 的 _get_model_config()
- src/deep_research/utils/llm.py 的 get_llm()
"""

import os
from typing import Optional, Union

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Aliyun DashScope 模型映射
ALIYUN_MODELS = {
    "qwen-max": "qwen-max",
    "qwen3-max": "qwen3-max",
    "kimi-k2-thinking": "kimi-k2-thinking",
    "deepseek-v3.2": "deepseek-v3.2",
}
DEFAULT_ALIYUN_MODEL = "qwen-max"

# OpenRouter 配置
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_OPENROUTER_MODEL = "anthropic/claude-sonnet-4.5"


def create_llm(
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
    enable_thinking: bool = False,
) -> Union[ChatOpenAI, ChatAnthropic]:
    """
    创建 LLM 实例。

    Args:
        model_provider: LLM 提供商 (aliyun, openai, anthropic, openrouter)。
        model_name: 具体的模型名称，未提供时使用默认值。
        enable_thinking: 是否启用思考模式（仅部分模型支持，如 qwen-max/kimi/DeepSeek via DashScope）。

    Returns:
        LLM 实例 (ChatOpenAI 或 ChatAnthropic)。

    Raises:
        ValueError: 未设置必要的 API key 或 provider 未知。
    """
    if model_provider == "aliyun":
        base_url = os.getenv(
            "ALIYUN_API_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        api_key = os.getenv("ALIYUN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("ALIYUN_API_KEY or DASHSCOPE_API_KEY environment variable not set")

        resolved_model = model_name
        if model_name in ALIYUN_MODELS:
            resolved_model = ALIYUN_MODELS[model_name]
        elif model_name is None:
            resolved_model = ALIYUN_MODELS[DEFAULT_ALIYUN_MODEL]

        extra_body = {"enable_thinking": True} if enable_thinking else None

        return ChatOpenAI(
            model=resolved_model,
            api_key=api_key,
            base_url=base_url,
            extra_body=extra_body,
            streaming=True,
        )
    elif model_provider == "openai":
        return ChatOpenAI(model=model_name or "gpt-4o")
    elif model_provider == "anthropic":
        return ChatAnthropic(model=model_name or "claude-sonnet-4-20250514")
    elif model_provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        resolved_model = model_name or DEFAULT_OPENROUTER_MODEL

        return ChatOpenAI(
            model=resolved_model,
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            streaming=True,
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", ""),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Research Agent"),
            },
        )
    else:
        raise ValueError(f"Unknown provider: {model_provider}")
