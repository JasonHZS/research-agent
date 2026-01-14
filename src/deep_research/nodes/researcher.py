"""
Researcher Node

通过 Send API 接收 Section，执行研究并返回更新后的 Section。
包含内部循环：researcher -> tools -> (循环或完成) -> 压缩输出
"""

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from src.prompts import load_prompt

from ..state import DeepResearchConfig, ResearcherOutputState, ResearcherState, Section
from ..structured_outputs import SectionContent, get_researcher_tools
from ..utils.display import render_tool_calls
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
        verbose=configurable.get("verbose", False),
    )


async def _researcher_invoke_node(
    state: ResearcherState,
    config: RunnableConfig,
    all_tools: list,
) -> dict:
    """
    Researcher 代理：调查特定章节。

    拥有所有搜索/阅读工具以及完成工具。
    """
    deep_config = _get_config(config)

    llm = get_llm(deep_config.model_provider, deep_config.model_name)

    # 构建 researcher 工具（所有研究工具 + 完成工具）
    researcher_tools = get_researcher_tools(all_tools)
    llm_with_tools = llm.bind_tools(researcher_tools)

    # 构建消息
    researcher_messages = get_state_value(state, "researcher_messages", [])
    section = get_state_value(state, "section", None)
    research_brief = get_state_value(state, "research_brief", "")
    messages = []

    # 从 Section 提取研究任务
    section_title = section.title if section else ""
    section_description = section.description if section else ""

    # 系统提示（首次调用时添加）
    if not researcher_messages:
        system_prompt = load_prompt(
            "deep_research/researcher",
            section_title=section_title,
            section_description=section_description,
            research_brief=research_brief,
        )
        messages.append(SystemMessage(content=system_prompt))
        messages.append(
            HumanMessage(content=f"请研究以下章节: {section_title}\n\n{section_description}")
        )

    messages.extend(researcher_messages)

    # 调用 LLM
    response = await llm_with_tools.ainvoke(messages)

    # 打印工具调用（如果 verbose 模式启用）
    if deep_config.verbose and hasattr(response, "tool_calls") and response.tool_calls:
        render_tool_calls(
            tool_calls=response.tool_calls,
            verbose=deep_config.verbose,
            section_title=section_title,
        )

    return {
        "researcher_messages": [response],
    }


async def _researcher_tools_node(
    state: ResearcherState,
    config: RunnableConfig,
    all_tools: list,
) -> dict:
    """
    执行 researcher 的工具调用。

    返回：
    - tool_call_iterations: 递增的计数
    - is_complete: 如果调用了 research_complete 则为 True
    - researcher_messages: 工具响应消息
    """
    researcher_tools = get_researcher_tools(all_tools)
    tool_node = ToolNode(researcher_tools)

    # 获取最新的 AI 消息
    researcher_messages = get_state_value(state, "researcher_messages", [])
    last_msg = researcher_messages[-1] if researcher_messages else None
    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        # 没有工具调用，标记完成
        return {
            "is_complete": True,
            "tool_call_iterations": get_state_value(state, "tool_call_iterations", 0) + 1,
        }

    # 检查是否调用了 research_complete
    for tool_call in last_msg.tool_calls:
        if tool_call["name"] == "research_complete":
            return {
                "is_complete": True,
                "tool_call_iterations": get_state_value(state, "tool_call_iterations", 0) + 1,
                "researcher_messages": [
                    ToolMessage(
                        content="研究已标记为完成",
                        tool_call_id=tool_call["id"],
                    )
                ],
            }

    # 执行工具调用
    result = await tool_node.ainvoke({"messages": [last_msg]})
    tool_messages = result.get("messages", [])

    return {
        "researcher_messages": tool_messages,
        "tool_call_iterations": get_state_value(state, "tool_call_iterations", 0) + 1,
    }


async def _compress_and_output_node(
    state: ResearcherState,
    config: RunnableConfig,
) -> ResearcherOutputState:
    """
    压缩研究发现并输出更新后的 Section。

    从工具响应和 AI 推理中提取关键发现，
    返回 status=completed 的 Section。
    """
    deep_config = _get_config(config)

    llm = get_llm(deep_config.model_provider, deep_config.model_name)

    # 从 researcher 消息中提取原始内容
    raw_content = []
    researcher_messages = get_state_value(state, "researcher_messages", [])
    section = get_state_value(state, "section", None)
    section_title = section.title if section else ""
    section_description = section.description if section else ""

    for msg in researcher_messages:
        if isinstance(msg, ToolMessage):
            raw_content.append(f"[Tool Result]\n{msg.content}")
        elif isinstance(msg, AIMessage) and msg.content:
            raw_content.append(f"[Analysis]\n{msg.content}")

    combined_content = "\n\n---\n\n".join(raw_content)

    # 加载压缩提示
    prompt_text = load_prompt(
        "deep_research/compress",
        section_title=section_title,
        section_description=section_description,
        raw_findings=combined_content[:50000],  # 限制以防止 token 溢出
    )

    try:
        llm_with_output = llm.with_structured_output(SectionContent)
        result: SectionContent = await llm_with_output.ainvoke(prompt_text)

        # 构建完成的 Section
        completed_section = Section(
            title=section_title,
            description=section_description,
            status="completed",
            content=result.content,
            sources=result.sources,
        )
    except Exception:
        # 回退：简单截断
        fallback_content = combined_content[:8000]
        completed_section = Section(
            title=section_title,
            description=section_description,
            status="completed",
            content=fallback_content,
            sources=[],
        )

    return {
        "sections": [completed_section],
    }


def build_researcher_subgraph(tools: list) -> StateGraph:
    """
    构建 researcher 子图。

    流程: researcher -> researcher_tools -> [循环或压缩] -> END
    """
    workflow = StateGraph(
        ResearcherState,
        output=ResearcherOutputState,
    )

    # 添加节点（使用闭包注入工具）
    async def researcher_invoke(state: ResearcherState, config: RunnableConfig):
        return await _researcher_invoke_node(state, config, tools)

    async def researcher_tools(state: ResearcherState, config: RunnableConfig):
        return await _researcher_tools_node(state, config, tools)

    workflow.add_node("researcher", researcher_invoke)
    workflow.add_node("researcher_tools", researcher_tools)
    workflow.add_node("compress_output", _compress_and_output_node)

    # 设置入口点
    workflow.add_edge(START, "researcher")

    # researcher -> researcher_tools
    workflow.add_edge("researcher", "researcher_tools")

    # researcher_tools 基于结果路由
    def route_researcher_tools(
        state: ResearcherState,
    ) -> Literal["researcher", "compress_output"]:
        is_complete = get_state_value(state, "is_complete", False)
        tool_call_iterations = get_state_value(state, "tool_call_iterations", 0)
        max_tool_calls = get_state_value(state, "max_tool_calls", 10)
        if is_complete or tool_call_iterations >= max_tool_calls:
            return "compress_output"
        return "researcher"

    workflow.add_conditional_edges(
        "researcher_tools",
        route_researcher_tools,
    )

    # compress_output -> END
    workflow.add_edge("compress_output", END)

    return workflow.compile()


# ============================================================================
# 简化版：单节点 Researcher（用于主图的 Send API）
# ============================================================================


async def researcher_node(
    state: ResearcherState,
    config: RunnableConfig,
    tools: list,
) -> ResearcherOutputState:
    """
    完整的 Researcher 节点：执行研究循环并返回 Section。

    这个节点作为主图的一部分，通过 Send API 接收输入。
    内部运行子图完成研究后返回更新的 Section。
    """
    # 构建并运行子图
    subgraph = build_researcher_subgraph(tools)

    # 准备输入状态
    section = get_state_value(state, "section", None)
    research_brief = get_state_value(state, "research_brief", "")

    input_state = {
        "section": section,
        "research_brief": research_brief,
        "max_tool_calls": get_state_value(state, "max_tool_calls", 10),
    }

    # 运行子图
    result = await subgraph.ainvoke(input_state, config)

    return result
