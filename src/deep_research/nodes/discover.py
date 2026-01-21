"""
Discover Node

整体发现/枚举阶段：执行广泛的检索，发现所有相关实体。
这是"先整体检索，再分别深入"策略的第一步。
"""

from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from langgraph.types import Command

from src.prompts import load_prompt
from src.utils.logging_config import get_logger

from ..state import AgentState, DeepResearchConfig, DiscoveredItem
from ..structured_outputs import DiscoveryResult, get_researcher_tools
from ..utils.llm import get_llm
from ..utils.state import get_state_value

import operator

logger = get_logger(__name__)
from typing import Annotated


# ==============================================================================
# 内部状态（用于发现子图）
# ==============================================================================


class DiscoverState(AgentState):
    """前置探索阶段的内部状态。"""

    # 使用 operator.add 累积消息，而不是替换
    discover_messages: Annotated[list, operator.add] = []
    discover_iterations: int = 0
    max_discover_iterations: int = 5  # 最多执行 5 轮搜索（避免递归限制）


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


# ==============================================================================
# 前置探索节点
# ==============================================================================


async def _discover_invoke_node(
    state: DiscoverState,
    config: RunnableConfig,
    all_tools: list,
) -> dict:
    """
    发现代理：执行广泛的整体检索。

    使用多种工具进行广度搜索，发现所有相关实体。
    """
    deep_config = _get_config(config)

    llm = get_llm(deep_config.model_provider, deep_config.model_name)

    # 构建工具（所有研究工具 + 完成工具）
    discover_tools = get_researcher_tools(all_tools)
    llm_with_tools = llm.bind_tools(discover_tools)

    # 构建消息
    discover_messages = get_state_value(state, "discover_messages", [])
    original_query = get_state_value(state, "original_query", "")

    # 始终包含系统提示和初始消息
    system_prompt = load_prompt(
        "deep_research/discover",
        query=original_query,
    )
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(
            content=f"请对以下查询进行整体发现/枚举检索，找出所有相关选项：\n\n{original_query}"
        ),
    ]

    # 追加历史消息
    messages.extend(discover_messages)

    # 调用 LLM
    response = await llm_with_tools.ainvoke(messages)

    return {
        "discover_messages": [response],
    }


async def _discover_tools_node(
    state: DiscoverState,
    config: RunnableConfig,
    all_tools: list,
) -> dict:
    """
    执行前置探索的工具调用。

    返回：
    - discover_iterations: 递增的计数
    - discovery_complete: 如果调用了 research_complete 则为 True
    - discover_messages: 工具响应消息
    """
    discover_tools = get_researcher_tools(all_tools)
    tool_node = ToolNode(discover_tools)

    # 获取最新的 AI 消息
    discover_messages = get_state_value(state, "discover_messages", [])
    last_msg = discover_messages[-1] if discover_messages else None

    if not isinstance(last_msg, AIMessage) or not last_msg.tool_calls:
        # 没有工具调用，标记完成
        return {
            "discovery_complete": True,
            "discover_iterations": get_state_value(state, "discover_iterations", 0)
            + 1,
        }

    # 检查是否调用了 research_complete
    for tool_call in last_msg.tool_calls:
        if tool_call["name"] == "research_complete":
            return {
                "discovery_complete": True,
                "discover_iterations": get_state_value(state, "discover_iterations", 0)
                + 1,
                "discover_messages": [
                    ToolMessage(
                        content="前置探索已完成",
                        tool_call_id=tool_call["id"],
                    )
                ],
            }

    # 执行工具调用
    result = await tool_node.ainvoke({"messages": [last_msg]})
    tool_messages = result.get("messages", [])

    return {
        "discover_messages": tool_messages,
        "discover_iterations": get_state_value(state, "discover_iterations", 0) + 1,
    }


async def _extract_and_output_node(
    state: DiscoverState,
    config: RunnableConfig,
) -> dict:
    """
    从前置探索的结果中提取实体列表。

    使用 LLM 结构化输出提取发现的所有实体。
    """
    deep_config = _get_config(config)

    llm = get_llm(deep_config.model_provider, deep_config.model_name)

    # 从 discover 消息中提取原始内容
    raw_content = []
    discover_messages = get_state_value(state, "discover_messages", [])
    original_query = get_state_value(state, "original_query", "")

    for msg in discover_messages:
        if isinstance(msg, ToolMessage):
            raw_content.append(f"[Search Result]\n{msg.content}")
        elif isinstance(msg, AIMessage) and msg.content:
            raw_content.append(f"[Analysis]\n{msg.content}")

    combined_content = "\n\n---\n\n".join(raw_content)

    # 从模板加载提取提示
    extract_prompt = load_prompt(
        "deep_research/extract_entities",
        original_query=original_query,
        search_results=combined_content[:50000],
    )

    try:
        llm_with_output = llm.with_structured_output(DiscoveryResult)
        result: DiscoveryResult = await llm_with_output.ainvoke(extract_prompt)

        # 转换为 DiscoveredItem
        discovered_items = [
            DiscoveredItem(
                name=entity.name,
                category=entity.category,
                brief=entity.brief,
                source=entity.source,
                urls=[],  # 后续阶段会填充
            )
            for entity in result.entities
        ]

        return {
            "discovered_items": discovered_items,
            "discovery_complete": True,
            "discovery_summary": result.summary,
        }

    except Exception as e:
        # 回退：返回空列表，让后续阶段自行处理
        return {
            "discovered_items": [],
            "discovery_complete": True,
            "discovery_summary": f"前置探索结果提取失败: {e}\n\n原始内容:\n{combined_content[:5000]}",
        }


# ==============================================================================
# 构建发现子图
# ==============================================================================


def build_discover_subgraph(tools: list) -> StateGraph:
    """
    构建前置探索子图。

    流程: discover -> discover_tools -> [循环或提取] -> END
    """
    workflow = StateGraph(DiscoverState)

    # 添加节点（使用闭包注入工具）
    async def discover_invoke(state: DiscoverState, config: RunnableConfig):
        return await _discover_invoke_node(state, config, tools)

    async def discover_tools(state: DiscoverState, config: RunnableConfig):
        return await _discover_tools_node(state, config, tools)

    workflow.add_node("discover", discover_invoke)
    workflow.add_node("discover_tools", discover_tools)
    workflow.add_node("extract_output", _extract_and_output_node)

    # 设置入口点
    workflow.add_edge(START, "discover")

    # discover -> discover_tools
    workflow.add_edge("discover", "discover_tools")

    # discover_tools 基于结果路由
    def route_discover_tools(
        state: DiscoverState,
    ) -> Literal["discover", "extract_output"]:
        discovery_complete = get_state_value(state, "discovery_complete", False)
        discover_iterations = get_state_value(state, "discover_iterations", 0)
        max_iterations = get_state_value(state, "max_discover_iterations", 5)

        logger.debug(
            "Discover iteration",
            iteration=discover_iterations,
            max_iterations=max_iterations,
            complete=discovery_complete,
        )
        print(f"  [Discover] 迭代 {discover_iterations}/{max_iterations}, 完成={discovery_complete}")

        if discovery_complete or discover_iterations >= max_iterations:
            return "extract_output"
        return "discover"

    workflow.add_conditional_edges(
        "discover_tools",
        route_discover_tools,
    )

    # extract_output -> END
    workflow.add_edge("extract_output", END)

    return workflow.compile()


# ==============================================================================
# 主图节点
# ==============================================================================


async def discover_node(
    state: AgentState,
    config: RunnableConfig,
    tools: list,
) -> dict:
    """
    发现节点：执行整体检索，发现所有相关实体。

    增强方案的核心节点，实现"先整体检索，再分别深入"策略。
    只对 list 类型查询执行，其他类型跳过。
    """
    query_type = get_state_value(state, "query_type", "general")

    # 非 list 类型查询，跳过前置探索
    if query_type != "list":
        return {
            "discovery_complete": True,
            "discovered_items": [],
            "discovery_summary": "",
        }

    # 构建并运行发现子图
    subgraph = build_discover_subgraph(tools)

    # 准备输入状态
    input_state = {
        "original_query": get_state_value(state, "original_query", ""),
        "query_type": query_type,
        "messages": get_state_value(state, "messages", []),
    }

    # 运行子图
    result = await subgraph.ainvoke(input_state, config)

    return {
        "discovered_items": result.get("discovered_items", []),
        "discovery_complete": True,
        "discovery_summary": result.get("discovery_summary", ""),
    }


# ==============================================================================
# 用于 graph.py 的简化接口
# ==============================================================================


async def run_discovery(
    state: AgentState,
    config: RunnableConfig,
    tools: list,
) -> Command:
    """
    运行前置探索并返回 Command 以继续到下一节点。

    这个函数直接返回 Command，方便在 graph.py 中使用。
    """
    result = await discover_node(state, config, tools)

    return Command(
        goto="plan_sections",
        update=result,
    )

