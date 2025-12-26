"""
LLM Utilities

为深度研究节点创建 LLM 实例的函数。
与 src/agent/research_agent.py 中的模型解析保持一致：
- 支持 Aliyun DashScope 兼容端点（需 ALIYUN_API_KEY 或 DASHSCOPE_API_KEY）
- 支持 enable_thinking（部分模型）
- 明确的默认模型别名映射
"""

import os
from typing import Optional, Union

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

# Available models on Aliyun DashScope
ALIYUN_MODELS = {
    "qwen-max": "qwen-max",
    "kimi-k2-thinking": "kimi-k2-thinking",
    "deepseek-v3.2": "deepseek-v3.2",
}
DEFAULT_ALIYUN_MODEL = "qwen-max"


def get_llm(
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
    enable_thinking: bool = False,
) -> Union[ChatOpenAI, ChatAnthropic]:
    """
    获取深度研究节点的 LLM 实例。

    Args:
        model_provider: LLM 提供商 (aliyun, openai, anthropic)。
        model_name: 具体的模型名称，未提供时使用默认映射。
        enable_thinking: 是否启用思考模式（仅部分模型支持，如 qwen-max/kimi/DeepSeek via DashScope）。

    Returns:
        LLM 实例。
    """
    if model_provider == "aliyun":
        base_url = os.getenv(
            "ALIYUN_API_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        api_key = os.getenv("ALIYUN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        if not api_key:
            raise ValueError("ALIYUN_API_KEY 或 DASHSCOPE_API_KEY 未设置")

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
    else:
        raise ValueError(f"Unknown provider: {model_provider}")
