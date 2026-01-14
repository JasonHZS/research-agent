"""
LLM Utilities

为深度研究节点提供 LLM 实例。
实际创建逻辑委托给 src/config/llm_factory。
"""

from typing import Optional, Union

from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from src.config.llm_factory import create_llm as _create_llm


def get_llm(
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
    enable_thinking: bool = False,
) -> Union[ChatOpenAI, ChatAnthropic]:
    """
    获取深度研究节点的 LLM 实例。

    Args:
        model_provider: LLM 提供商 (aliyun, openai, anthropic, openrouter)。
        model_name: 具体的模型名称，未提供时使用默认值。
        enable_thinking: 是否启用思考模式（仅部分模型支持）。

    Returns:
        LLM 实例。
    """
    return _create_llm(model_provider, model_name, enable_thinking)
