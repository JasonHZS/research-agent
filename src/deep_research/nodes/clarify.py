"""
Clarify With User Node

分析用户查询，判断是否需要澄清。
简化设计：单节点内完成工具调用和澄清判断。
通过 Command API 控制流转移。
"""

import logging
from datetime import datetime
from typing import Literal

from langchain_core.messages import (
    AIMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
    get_buffer_string,
)
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END
from langgraph.types import Command

from src.prompts import load_prompt

from ..config import parse_deep_research_config
from ..state import AgentState, ClarificationStatus
from ..structured_outputs import ClarifyWithUser
from ..utils.display import render_tool_calls
from ..utils.llm import get_llm
from ..utils.state import get_state_value

logger = logging.getLogger(__name__)


def _get_clarify_tools() -> list:
    """获取澄清阶段可用的搜索工具。"""
    from src.tools.bocha_search import bocha_web_search_tool

    return [bocha_web_search_tool]


async def clarify_with_user_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["analyze", "__end__"]]:
    """
    分析用户查询，决定是否需要澄清。

    简化设计：单节点内完成工具调用和澄清判断。

    使用 Command API 控制流转移：
    - 如果需要澄清：goto=END，将澄清问题作为 AIMessage 添加到 messages
    - 如果查询清晰：goto="analyze"，将确认消息作为 AIMessage 添加到 messages

    Args:
        state: 当前 agent 状态，包含用户消息
        config: 运行时配置

    Returns:
        Command 对象，包含下一节点和状态更新
    """
    # 获取配置
    deep_config = parse_deep_research_config(config)
    messages = get_state_value(state, "messages", [])

    # 从 messages 中提取用户的完整意图作为 original_query
    user_messages = [m.content for m in messages if isinstance(m, HumanMessage)]
    original_query = "\n".join(user_messages) if user_messages else ""

    # 如果禁用澄清，直接跳过进入 analyze
    if not deep_config.allow_clarification:
        return Command(
            goto="analyze",
            update={"original_query": original_query},
        )

    # 获取工具和 LLM
    tools = _get_clarify_tools()
    llm = get_llm(deep_config.model_provider, deep_config.model_name)
    llm_with_tools = llm.bind_tools(tools)

    current_date = datetime.now().strftime("%Y-%m-%d")

    # 构建系统提示（角色设定、行为准则）
    system_prompt = load_prompt(
        "deep_research/clarify",
        query=get_buffer_string(messages),
        current_date=current_date,
    )

    # 工具调用循环（最多 2 轮）
    search_context = ""
    max_iterations = 2
    tool_messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content="请分析用户查询，判断是否需要澄清。如需实时信息可使用搜索工具。"
        ),
    ]

    # 收集工具调用日志（用于前端显示）
    clarify_tool_calls_log: list = []

    for i in range(max_iterations):
        response = await llm_with_tools.ainvoke(tool_messages)

        if not response.tool_calls:
            break

        # CLI verbose 模式打印（复用统一格式）
        if deep_config.verbose:
            render_tool_calls(
                response.tool_calls, verbose=True, section_title="Clarify"
            )

        # 收集 AIMessage (with tool_calls) 用于前端显示
        clarify_tool_calls_log.append(response)

        # 执行工具调用
        tool_results = []
        for tool_call in response.tool_calls:
            tool = next((t for t in tools if t.name == tool_call["name"]), None)
            if tool:
                result = await tool.ainvoke(tool_call["args"])
                tool_results.append(
                    ToolMessage(
                        content=result,
                        tool_call_id=tool_call["id"],
                    )
                )
                search_context += result + "\n\n"

        # 收集 ToolMessage 用于前端显示
        clarify_tool_calls_log.extend(tool_results)

        # 追加到消息历史
        tool_messages.append(response)
        tool_messages.extend(tool_results)

        logger.debug(
            "Clarify search iteration completed",
            iteration=i + 1,
            max_iterations=max_iterations,
        )
        print(f"  [Clarify] 搜索迭代 {i + 1}/{max_iterations} 完成")

    # 使用结构化输出提取最终决策（直接传字符串，和原版一致）
    final_prompt = load_prompt(
        "deep_research/clarify",
        query=get_buffer_string(messages),
        current_date=current_date,
        search_context=search_context,
    )

    try:
        llm_structured = llm.with_structured_output(ClarifyWithUser)
        result: ClarifyWithUser = await llm_structured.ainvoke(final_prompt)
    except Exception as e:
        # 回退：默认不需要澄清
        logger.warning(
            "Clarify result extraction failed",
            error=str(e),
            error_type=type(e).__name__,
        )
        print(f"  [Clarify] 结果提取失败: {e}")
        result = ClarifyWithUser(
            need_clarification=False,
            question="",
            verification="了解，我现在开始为您进行深度研究。",
        )

    # 日志打印原始决策 JSON（供调试，不发送到前端）
    logger.info(f"Clarify decision: {result.model_dump_json()}")
    print(
        f"\n[ClarifyWithUser]: "
        f"{result.verification if not result.need_clarification else result.question}"
    )

    if result.need_clarification:
        # 需要澄清：中断并等待用户响应
        # 通过 clarification_status 字段传递结构化决策，避免下游解析 JSON
        return Command(
            goto=END,
            update={
                "messages": [AIMessage(content=result.question)],
                "clarification_status": ClarificationStatus(
                    need_clarification=True,
                    question=result.question,
                    verification="",
                ),
                "original_query": original_query,
                "tool_calls_log": clarify_tool_calls_log,
            },
        )
    else:
        # 不需要澄清：继续进入 analyze（查询分析节点）
        return Command(
            goto="analyze",
            update={
                "messages": [AIMessage(content=result.verification)],
                "clarification_status": ClarificationStatus(
                    need_clarification=False,
                    question="",
                    verification=result.verification,
                ),
                "original_query": original_query,
                "tool_calls_log": clarify_tool_calls_log,
            },
        )
