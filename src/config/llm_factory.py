"""
LLM Factory

统一的 LLM 实例创建模块。
支持 aliyun, anthropic, openai, openrouter 四种 provider。

该模块整合了之前分散在多处的 LLM 创建逻辑：
- src/agent/research_agent.py 的 _get_model_config()
- src/deep_research/utils/llm.py 的 get_llm()
"""

import os
import warnings
from typing import Optional, Union

import httpx
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Streaming 场景下的超时配置
# connect: 建立连接超时
# read: 读取响应超时（streaming 时需要更长）
# write: 发送请求超时
# pool: 从连接池获取连接超时
DEFAULT_TIMEOUT = httpx.Timeout(
    connect=30.0,
    read=300.0,  # streaming 响应可能持续较长时间
    write=30.0,
    pool=30.0,
)

# Aliyun DashScope 模型映射
ALIYUN_MODELS = {
    "qwen-max": "qwen-max",
    "qwen3.5-plus": "qwen3.5-plus",
    "qwen3-max": "qwen3-max",
    "kimi-k2-thinking": "kimi-k2-thinking",
    "kimi-k2.5": "kimi-k2.5",
    "deepseek-v3.2": "deepseek-v3.2",
    "glm-5": "glm-5",
    # MiniMax-M2.1 暂不支持：模型在处理 Function Calling 时返回非 JSON 格式的 arguments
    # 错误: "The 'function.arguments' parameter of the code model must be in JSON format."
    # "minimax-m2.1": "MiniMax-M2.1",
}
DEFAULT_ALIYUN_MODEL = "qwen3.5-plus"

# OpenRouter 配置
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_MODELS = {
    "claude-sonnet-4.5": "anthropic/claude-sonnet-4.5",
    "gpt-5": "openai/gpt-5",
    "gemini-3-flash": "google/gemini-3-flash-preview",
    "minimax-m2.5": "minimax/minimax-m2.5",
}
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
        enable_thinking: 是否启用思考模式（仅部分模型支持，如 qwen3.5-plus/qwen-max/kimi/DeepSeek/GLM via DashScope）。

    Returns:
        LLM 实例 (ChatOpenAI 或 ChatAnthropic)。

    Raises:
        ValueError: 未设置必要的 API key 或 provider 未知。
    """
    if enable_thinking and model_provider != "aliyun":
        warnings.warn(
            f"enable_thinking=True is only supported for the 'aliyun' provider, "
            f"but got '{model_provider}'. The parameter will be ignored.",
            UserWarning,
            stacklevel=2,
        )

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
            max_retries=5,  # SDK 层面自动重试
            timeout=DEFAULT_TIMEOUT,  # 细粒度超时配置
        )
    elif model_provider == "openai":
        return ChatOpenAI(
            model=model_name or "gpt-4o",
            max_retries=5,
            timeout=DEFAULT_TIMEOUT,
        )
    elif model_provider == "anthropic":
        return ChatAnthropic(
            model=model_name or "claude-sonnet-4-20250514",
            max_retries=5,
            timeout=DEFAULT_TIMEOUT,
        )
    elif model_provider == "openrouter":
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            raise ValueError("OPENROUTER_API_KEY environment variable not set")

        # 支持简短别名（如 "gpt-5"）或完整模型名（如 "openai/gpt-5"）
        resolved_model = model_name
        if model_name in OPENROUTER_MODELS:
            resolved_model = OPENROUTER_MODELS[model_name]
        elif model_name is None:
            resolved_model = DEFAULT_OPENROUTER_MODEL

        return ChatOpenAI(
            model=resolved_model,
            api_key=api_key,
            base_url=OPENROUTER_BASE_URL,
            streaming=True,
            # 增加重试次数和超时配置以应对 OpenRouter 连接不稳定
            max_retries=5,  # SDK 层面自动重试
            timeout=DEFAULT_TIMEOUT,  # 细粒度超时配置
            default_headers={
                "HTTP-Referer": os.getenv("OPENROUTER_REFERER", ""),
                "X-Title": os.getenv("OPENROUTER_APP_TITLE", "Research Agent"),
            },
        )
    else:
        raise ValueError(f"Unknown provider: {model_provider}")
