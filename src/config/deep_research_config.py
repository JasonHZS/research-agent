"""
Deep Research Mode Configuration

Supervisor-Researcher 深度研究模式的配置设置。
"""

import os
from typing import Optional


# ==============================================================================
# 默认值
# ==============================================================================

DEFAULT_MAX_ITERATIONS = 3
DEFAULT_MAX_CONCURRENT_RESEARCHERS = 3
DEFAULT_MAX_TOOL_CALLS = 10

# ==============================================================================
# 环境变量名
# ==============================================================================

ENV_MAX_ITERATIONS = "DEEP_RESEARCH_MAX_ITERATIONS"
ENV_MAX_CONCURRENT = "DEEP_RESEARCH_MAX_CONCURRENT"
ENV_MAX_TOOL_CALLS = "DEEP_RESEARCH_MAX_TOOL_CALLS"
ENV_ALLOW_CLARIFICATION = "DEEP_RESEARCH_ALLOW_CLARIFICATION"


# ==============================================================================
# 配置函数
# ==============================================================================


def get_max_iterations(override: Optional[int] = None) -> int:
    """
    获取 supervisor 的最大迭代轮数。

    解析顺序：
    1. CLI 参数覆盖
    2. 环境变量 DEEP_RESEARCH_MAX_ITERATIONS
    3. 默认值 (3)

    Args:
        override: CLI 参数的覆盖值。

    Returns:
        最大迭代轮数（限制在 1-10 范围内）。
    """
    if override is not None:
        return max(1, min(10, override))

    env_value = os.getenv(ENV_MAX_ITERATIONS)
    if env_value:
        try:
            return max(1, min(10, int(env_value)))
        except ValueError:
            pass

    return DEFAULT_MAX_ITERATIONS


def get_max_concurrent_researchers(override: Optional[int] = None) -> int:
    """
    获取最大并发 researcher 数量。

    解析顺序：
    1. CLI 参数覆盖
    2. 环境变量 DEEP_RESEARCH_MAX_CONCURRENT
    3. 默认值 (5)

    Args:
        override: CLI 参数的覆盖值。

    Returns:
        最大并发数（限制在 1-10 范围内）。
    """
    if override is not None:
        return max(1, min(10, override))

    env_value = os.getenv(ENV_MAX_CONCURRENT)
    if env_value:
        try:
            return max(1, min(10, int(env_value)))
        except ValueError:
            pass

    return DEFAULT_MAX_CONCURRENT_RESEARCHERS


def get_max_tool_calls(override: Optional[int] = None) -> int:
    """
    获取每个 researcher 的最大工具调用数。

    解析顺序：
    1. CLI 参数覆盖
    2. 环境变量 DEEP_RESEARCH_MAX_TOOL_CALLS
    3. 默认值 (10)

    Args:
        override: CLI 参数的覆盖值。

    Returns:
        最大工具调用数（限制在 1-20 范围内）。
    """
    if override is not None:
        return max(1, min(20, override))

    env_value = os.getenv(ENV_MAX_TOOL_CALLS)
    if env_value:
        try:
            return max(1, min(20, int(env_value)))
        except ValueError:
            pass

    return DEFAULT_MAX_TOOL_CALLS


def get_allow_clarification(override: Optional[bool] = None) -> bool:
    """
    获取是否允许用户澄清。

    解析顺序：
    1. CLI 参数覆盖
    2. 环境变量 DEEP_RESEARCH_ALLOW_CLARIFICATION
    3. 默认值 (True)

    Args:
        override: CLI 参数的覆盖值。

    Returns:
        是否允许澄清。
    """
    if override is not None:
        return override

    env_value = os.getenv(ENV_ALLOW_CLARIFICATION)
    if env_value:
        return env_value.lower() in ("true", "1", "yes", "on")

    return True


def get_deep_research_settings(
    max_iterations_override: Optional[int] = None,
    max_concurrent_override: Optional[int] = None,
    max_tool_calls_override: Optional[int] = None,
    allow_clarification_override: Optional[bool] = None,
) -> dict:
    """
    获取所有深度研究配置设置。

    Args:
        max_iterations_override: 最大迭代轮数覆盖。
        max_concurrent_override: 最大并发数覆盖。
        max_tool_calls_override: 最大工具调用数覆盖。
        allow_clarification_override: 是否允许澄清覆盖。

    Returns:
        包含所有深度研究设置的字典。
    """
    return {
        "max_iterations": get_max_iterations(max_iterations_override),
        "max_concurrent_researchers": get_max_concurrent_researchers(
            max_concurrent_override
        ),
        "max_tool_calls_per_researcher": get_max_tool_calls(max_tool_calls_override),
        "allow_clarification": get_allow_clarification(allow_clarification_override),
    }
