"""
Plan Sections Node

将用户查询转换为结构化研究简报和章节列表。
使用 Command API 控制路由，直接派发 researcher 任务。
"""

from langchain_core.messages import get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Send

from src.prompts import load_prompt

from ..state import AgentState, DeepResearchConfig, Section
from ..structured_outputs import ResearchBrief
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
        model_name=configurable.get("model_name", "qwen-max"),
        enable_thinking=configurable.get("enable_thinking", False),
        allow_clarification=configurable.get("allow_clarification", True),
    )


async def plan_sections_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command:
    """
    从用户查询生成结构化研究简报和章节列表。

    使用 Command API 控制路由：
    - 生成/获取 sections 后，直接派发 researcher 任务（Send）
    - 如果已有 sections（review 循环回来），跳过重新生成，直接派发 pending 的章节

    返回：
    - Command(goto=[Send, ...], update={...})
    """
    deep_config = _get_config(config)
    max_tool_calls = deep_config.max_tool_calls_per_researcher

    # 检查是否已有 sections（review 循环回来的情况）
    existing_sections = get_state_value(state, "sections", [])
    research_brief = get_state_value(state, "research_brief", "")

    if existing_sections:
        # 已有 sections，说明是 review 循环回来的，跳过重新生成
        pending_sections = [s for s in existing_sections if s.status == "pending"]
        print(f"\n[Brief]: 跳过重新生成（已有 {len(existing_sections)} 个章节，{len(pending_sections)} 个待研究）\n")

        # 直接派发 pending 的章节
        sends = [
            Send(
                "researcher",
                {
                    "section": s,
                    "research_brief": research_brief,
                    "max_tool_calls": max_tool_calls,
                },
            )
            for s in pending_sections
        ]
        return Command(goto=sends)

    # 首次生成研究大纲
    llm = get_llm(deep_config.model_provider, deep_config.model_name)
    llm_with_output = llm.with_structured_output(ResearchBrief)

    # 使用完整消息历史（用户问题 + AI澄清 + 用户回答）
    messages = get_state_value(state, "messages", [])

    # 加载规划提示
    prompt_text = load_prompt(
        "deep_research/plan",
        query=get_buffer_string(messages),
    )

    result: ResearchBrief = await llm_with_output.ainvoke(prompt_text)

    # 打印研究大纲
    print(f"\n[Brief]: {result.title}")
    print(f"  目标: {result.objective}")
    print(f"  范围: {result.scope}")
    print(f"  章节: {', '.join(s.title for s in result.sections)}\n")

    # 将 SectionPlan 转换为 Section 对象
    sections = [
        Section(
            title=s.title,
            description=s.description,
            status="pending",
            content="",
            sources=[],
        )
        for s in result.sections
    ]

    # 将简报格式化为文本
    sections_text = "\n".join(
        f"- **{s.title}**: {s.description}" for s in result.sections
    )
    brief_text = f"""# {result.title}

## 研究目标
{result.objective}

## 研究范围
{result.scope}

## 研究章节
{sections_text}
"""

    # 构建 Send 列表，派发所有 researcher 任务
    sends = [
        Send(
            "researcher",
            {
                "section": s,
                "research_brief": brief_text,
                "max_tool_calls": max_tool_calls,
            },
        )
        for s in sections
    ]

    # 使用 Command 同时更新状态并派发任务
    return Command(
        goto=sends,
        update={
            "research_brief": brief_text,
            "sections": sections,
            "max_review_iterations": deep_config.max_review_iterations,
        },
    )


# 保留旧名称作为别名以兼容
write_research_brief_node = plan_sections_node
