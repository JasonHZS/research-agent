"""
Deep Research Graph Construction

构建基于 Section 的深度研究图（增强方案）：
1. clarify -> analyze -> discover (list类型) -> plan_sections -> [Send: researcher] 
   -> aggregate -> review -> (loop or) final_report

使用 LangGraph Command + Send API 实现原生图级别的并行研究。
节点使用 Command API 控制路由，简化图结构。

增强方案：
- 添加 analyze 节点识别查询类型
- 添加 discover 节点执行"整体发现"
- 对于 list 类型查询，先发现所有实体，再为每个实体生成专门章节
"""

from typing import Literal, Optional

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command

from .nodes import (
    analyze_query_node,
    clarify_with_user_node,
    discover_node,
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

    # 打印调试信息
    completed = sum(1 for s in sections if s.status == "completed")
    total = len(sections)
    print(f"\n[Aggregate]: {completed}/{total} 章节已完成\n")

    # 返回空更新，状态已通过 reducer 更新
    return {}


# ==============================================================================
# 主图构建
# ==============================================================================


from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.store.base import BaseStore

def build_deep_research_graph(
    hn_mcp_tools: Optional[list] = None,
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
    checkpointer: Optional[BaseCheckpointSaver] = None,
    store: Optional[BaseStore] = None,
) -> StateGraph:
    """
    构建完整的深度研究图。

    流程:
    clarify -> analyze -> discover (list类型) -> plan_sections -> dispatch (Send) 
                            |                ^
                            |                |
                            +-- (其他类型) ---+
                                             |
    -> researcher -> aggregate -> review ->   (loop or) final_report -> END
           ^                         |
           |_________________________| (if gaps exist)

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

    # === 创建 discover 节点的闭包（注入工具） ===
    async def discover_wrapper(
        state: AgentState, config: RunnableConfig
    ) -> Command[Literal["plan_sections"]]:
        result = await discover_node(state, config, all_tools)
        # 返回 Command 跳转到 plan_sections
        return Command(
            goto="plan_sections",
            update=result,
        )

    # 添加节点
    workflow.add_node("clarify", clarify_with_user_node)
    workflow.add_node("analyze", analyze_query_node)  # 增强方案：查询分析
    workflow.add_node("discover", discover_wrapper)  # 增强方案：前置探索
    workflow.add_node("plan_sections", plan_sections_node)
    workflow.add_node("researcher", researcher_subgraph)  # 接收 Send 的并行任务
    workflow.add_node("aggregate", aggregate_sections_node)
    workflow.add_node("review", review_node)
    workflow.add_node("final_report", final_report_node)

    # 设置入口点
    workflow.add_edge(START, "clarify")

    # clarify 使用 Command API 控制路由：
    # - Command(goto="analyze") 继续分析
    # - Command(goto=END) 需要用户回答澄清问题

    # analyze 使用 Command API 控制路由：
    # - Command(goto="discover") 如果是 list 类型查询
    # - Command(goto="plan_sections") 其他类型

    # discover 使用 Command API 跳转到 plan_sections

    # plan_sections 使用 Command API 控制路由，直接派发 Send 到 researcher
    # Command(goto=[Send("researcher", ...), ...]) 实现并行分发

    # researcher -> aggregate (Fan-in)
    workflow.add_edge("researcher", "aggregate")

    # aggregate -> review
    workflow.add_edge("aggregate", "review")

    # review 使用 Command API 控制路由：
    # - Command(goto="plan_sections") 如果需要重新研究
    # - Command(goto="final_report") 如果信息充足

    # final_report -> END
    workflow.add_edge("final_report", END)

    return workflow.compile(checkpointer=checkpointer, store=store)


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
    # 确保设置了足够的递归限制
    # LangGraph 默认 recursion_limit=25，但深度研究涉及多轮工具调用，容易超限
    # 该参数会传递给 graph.ainvoke()，由 LangGraph 内部检查执行步数
    if "recursion_limit" not in config:
        config["recursion_limit"] = 100

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
