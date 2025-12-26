"""
Clarify With User Node

分析用户查询，判断是否需要澄清。
使用结构化输出进行决策，通过 Command API 控制流转移。
"""

from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from src.prompts import load_prompt

from ..state import AgentState, DeepResearchConfig
from ..structured_outputs import ClarifyWithUser
from ..utils.llm import get_llm
from ..utils.state import get_state_value


def _get_config(config: RunnableConfig) -> DeepResearchConfig:
    """从 RunnableConfig 中提取 DeepResearchConfig。"""
    configurable = config.get("configurable", {})
    return DeepResearchConfig(
        max_tool_calls_per_researcher=configurable.get(
            "max_tool_calls_per_researcher", 10
        ),
        max_review_iterations=configurable.get("max_review_iterations", 2),
        model_provider=configurable.get("model_provider", "aliyun"),
        model_name=configurable.get("model_name"),
        enable_thinking=configurable.get("enable_thinking", False),
        allow_clarification=configurable.get("allow_clarification", True),
    )


async def clarify_with_user_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["plan_sections", "__end__"]]:
    """
    分析用户查询，决定是否需要澄清。

    使用 Command API 控制流转移：
    - 如果需要澄清：goto=END，将澄清问题作为 AIMessage 添加到 messages
    - 如果查询清晰：goto="plan_sections"，将确认消息作为 AIMessage 添加到 messages

    Args:
        state: 当前 agent 状态，包含用户消息
        config: 运行时配置

    Returns:
        Command 对象，包含下一节点和状态更新
    """
    # 获取配置
    deep_config = _get_config(config)
    messages = get_state_value(state, "messages", [])

    # 从 messages 中提取用户的完整意图作为 original_query
    # 包含所有用户消息（初始查询 + 澄清回答）
    user_messages = [m.content for m in messages if isinstance(m, HumanMessage)]
    original_query = "\n".join(user_messages) if user_messages else ""

    # 如果禁用澄清，直接跳过进入 plan_sections
    if not deep_config.allow_clarification:
        return Command(
            goto="plan_sections",
            update={"original_query": original_query},
        )

    # 获取带结构化输出的 LLM
    llm = get_llm(deep_config.model_provider, deep_config.model_name)
    llm_with_output = llm.with_structured_output(ClarifyWithUser)

    # 获取当前日期
    current_date = datetime.now().strftime("%Y-%m-%d")

    # 加载提示并调用（使用 get_buffer_string 格式化完整消息历史）
    prompt_text = load_prompt(
        "deep_research/clarify",
        query=get_buffer_string(messages),
        current_date=current_date,
    )

    result: ClarifyWithUser = await llm_with_output.ainvoke(prompt_text)
    print("\n[ClarifyWithUser]:", result.verification)

    if result.need_clarification:
        # 需要澄清：中断并等待用户响应
        return Command(
            goto=END,
            update={
                "messages": [AIMessage(content=result.question)],
                "original_query": original_query,
            },
        )
    else:
        # 不需要澄清：继续进入 plan_sections
        # 设置 original_query 供后续节点使用
        return Command(
            goto="plan_sections",
            update={
                "messages": [AIMessage(content=result.verification)],
                "original_query": original_query,
            },
        )
