"""
Context Compression Utilities

管理上下文窗口和压缩消息的函数。
"""

from typing import List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage


def estimate_tokens(text: str) -> int:
    """
    粗略估计 token 数量（平均每 4 个字符 1 个 token）。

    对于精确计数，请使用 tiktoken 与具体模型。
    """
    if not text:
        return 0
    return len(text) // 4


def compress_messages(
    messages: List[BaseMessage],
    max_tokens: int = 8000,
) -> str:
    """
    将消息列表压缩为摘要字符串。

    优先级：
    1. 工具结果（实际内容）
    2. AI 分析/推理
    3. Human 消息（上下文）

    Args:
        messages: 要压缩的消息列表。
        max_tokens: 输出的目标 token 数。

    Returns:
        消息的压缩文本表示。
    """
    # 按类型分离
    tool_results = []
    ai_analysis = []

    for msg in messages:
        if isinstance(msg, ToolMessage) and msg.content:
            tool_results.append(str(msg.content))
        elif isinstance(msg, AIMessage) and msg.content:
            ai_analysis.append(str(msg.content))

    # 构建压缩输出
    parts = []
    remaining_tokens = max_tokens

    # 首先添加工具结果（优先级最高）
    for result in tool_results:
        tokens = estimate_tokens(result)
        if tokens <= remaining_tokens:
            parts.append(f"[Tool Result]\n{result}")
            remaining_tokens -= tokens
        else:
            # 如果太长则截断
            truncated = result[: remaining_tokens * 4]
            parts.append(f"[Tool Result - Truncated]\n{truncated}...")
            break

    # 如果还有空间，添加 AI 分析
    for analysis in ai_analysis:
        tokens = estimate_tokens(analysis)
        if tokens <= remaining_tokens:
            parts.append(f"[Analysis]\n{analysis}")
            remaining_tokens -= tokens

    return "\n\n---\n\n".join(parts)


def should_compress(messages: List[BaseMessage], threshold: int = 80000) -> bool:
    """
    检查消息是否应该基于 token 数量进行压缩。

    Args:
        messages: 要检查的消息列表。
        threshold: 触发压缩的 token 阈值。

    Returns:
        如果建议压缩则返回 True。
    """
    total_tokens = sum(
        estimate_tokens(str(msg.content)) for msg in messages if msg.content
    )
    return total_tokens > threshold


def remove_up_to_last_ai_message(messages: List[BaseMessage]) -> List[BaseMessage]:
    """
    移除从最后一条 AI 消息开始的所有内容。

    用于 token 限制恢复时逐步截断消息。

    Args:
        messages: 消息列表。

    Returns:
        截断后的消息列表。
    """
    for i in range(len(messages) - 1, -1, -1):
        if isinstance(messages[i], AIMessage):
            return messages[:i]
    return messages


def filter_messages(
    messages: List[BaseMessage],
    include_types: List[str] = None,
) -> List[BaseMessage]:
    """
    按类型过滤消息。

    Args:
        messages: 消息列表。
        include_types: 要包含的消息类型（'tool', 'ai', 'human'）。

    Returns:
        过滤后的消息列表。
    """
    if include_types is None:
        return messages

    type_map = {
        "tool": ToolMessage,
        "ai": AIMessage,
        "human": HumanMessage,
    }

    target_types = tuple(type_map[t] for t in include_types if t in type_map)
    return [msg for msg in messages if isinstance(msg, target_types)]
