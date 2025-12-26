"""
Deep Research Graph Construction

构建基于 Section 的深度研究图：
1. clarify -> plan_sections -> [Send: researcher] -> aggregate -> review -> (loop or) final_report

使用 LangGraph Command + Send API 实现原生图级别的并行研究。
节点使用 Command API 控制路由，简化图结构。
"""

from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from .nodes import (
    clarify_with_user_node,
    final_report_node,
    plan_sections_node,
    review_node,
)
from .nodes.researcher import build_researcher_subgraph
from .state import (
    AgentInputState,
    AgentOutputState,
    AgentState,
)
from .utils.tools import get_all_research_tools
from .utils.state import get_state_value


# ==============================================================================
# 辅助节点：Aggregate
# ==============================================================================


async def aggregate_sections_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict:
    """
    聚合所有 researcher 返回的 Section 更新。

    这个节点作为 Send 并行执行后的汇聚点。
    由于 section_reducer 已经处理了合并逻辑，
    这个节点主要是一个同步点，不需要额外逻辑。
    """
    # 检查是否所有 section 都已完成
    sections = get_state_value(state, "sections", [])

    # 打印调试信息（可选）
    completed = sum(1 for s in sections if s.status == "completed")
    total = len(sections)

    # 返回空更新，状态已通过 reducer 更新
    return {}


# ==============================================================================
# 路由函数
# ==============================================================================


def route_after_review(
    state: AgentState,
) -> Literal["dispatch", "final_report"]:
    """
    Review 后的路由：

    - 如果有 pending 的 section 且未达到最大迭代次数 -> 回到 dispatch
    - 否则 -> 生成最终报告
    """
    sections = get_state_value(state, "sections", [])
    review_iterations = get_state_value(state, "review_iterations", 0)
    max_review_iterations = get_state_value(state, "max_review_iterations", 2)

    # 检查是否达到最大迭代次数
    if review_iterations >= max_review_iterations:
        return "final_report"

    # 检查是否有 pending 的 section
    pending = [s for s in sections if s.status == "pending"]
    if pending:
        return "dispatch"

    return "final_report"


# ==============================================================================
# 主图构建
# ==============================================================================


def build_deep_research_graph(
    hn_mcp_tools: Optional[list] = None,
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
) -> StateGraph:
    """
    构建完整的深度研究图。

    流程:
    clarify -> plan_sections -> dispatch (Send) -> researcher -> aggregate -> review
                                    ^                                           |
                                    |___________________________________________|
                                                    (if gaps exist)
                                                           |
                                                           v
                                                    final_report -> END

    Args:
        hn_mcp_tools: Hacker News MCP 工具（可选）。
        model_provider: LLM 提供商。
        model_name: 具体模型名称。

    Returns:
        编译后的 StateGraph，准备执行。
    """
    # 组装所有研究工具
    all_tools = get_all_research_tools(hn_mcp_tools)

    # 构建 researcher 子图
    researcher_subgraph = build_researcher_subgraph(all_tools)

    # 构建主图
    workflow = StateGraph(
        AgentState,
        input=AgentInputState,
        output=AgentOutputState,
    )

    # 添加节点
    workflow.add_node("clarify", clarify_with_user_node)
    workflow.add_node("plan_sections", plan_sections_node)
    workflow.add_node("researcher", researcher_subgraph)  # 接收 Send 的并行任务
    workflow.add_node("aggregate", aggregate_sections_node)
    workflow.add_node("review", review_node)
    workflow.add_node("final_report", final_report_node)

    # 设置入口点
    workflow.add_edge(START, "clarify")

    # clarify 使用 Command API 控制路由，不需要添加静态边
    # Command(goto="plan_sections") 或 Command(goto=END) 直接决定下一节点

    # plan_sections 使用 Command API 控制路由，直接派发 Send 到 researcher
    # Command(goto=[Send("researcher", ...), ...]) 实现并行分发
    # 不需要添加静态边，Command 会自动处理

    # researcher -> aggregate (Fan-in)
    workflow.add_edge("researcher", "aggregate")

    # aggregate -> review
    workflow.add_edge("aggregate", "review")

    # review -> dispatch 或 final_report
    workflow.add_conditional_edges(
        "review",
        route_after_review,
        {
            "dispatch": "plan_sections",  # 回到 plan_sections 会重新触发 dispatch
            "final_report": "final_report",
        },
    )

    # final_report -> END
    workflow.add_edge("final_report", END)

    return workflow.compile()


# ==============================================================================
# 辅助运行函数
# ==============================================================================


async def run_deep_research(
    query: str,
    graph,
    config: dict,
    on_clarify_question: Optional[callable] = None,
) -> str:
    """
    运行深度研究图，支持人在环澄清。

    Args:
        query: 用户的研究查询。
        graph: 编译后的深度研究图。
        config: RunnableConfig 配置字典。
        on_clarify_question: 获取用户回答的回调函数。
                            签名: async (question: str) -> str

    Returns:
        最终研究报告。
    """
    # 初始状态
    initial_state = {
        "messages": [HumanMessage(content=query)],
    }

    # 运行，可能有澄清中断
    current_state = initial_state

    while True:
        # 运行图
        result = await graph.ainvoke(current_state, config)
        if result is None:
            # 防御：LLM/节点异常导致返回 None 时避免崩溃
            result = {}

        # 检查是否需要澄清：
        # - 没有 final_report（图在 clarify 阶段中断）
        # - 最后一条消息是 AIMessage（澄清问题）
        messages = result.get("messages", [])
        final_report = result.get("final_report", "")

        if not final_report and messages:
            last_message = messages[-1]
            if isinstance(last_message, AIMessage):
                # 这是一个澄清问题
                clarification_question = last_message.content
                if on_clarify_question:
                    # 获取用户回答
                    answer = await on_clarify_question(clarification_question)
                    # 用回答更新状态并继续
                    current_state = dict(result)
                    current_state["messages"] = list(messages)
                    current_state["messages"].append(HumanMessage(content=answer))
                    continue
                else:
                    # 没有回调，无法处理澄清，返回空报告
                    break

        # 图完成（有 final_report 或无需澄清）
        break

    return result.get("final_report", "")
