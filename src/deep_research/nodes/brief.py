"""
Plan Sections Node

将用户查询转换为结构化研究简报和章节列表。
使用 Command API 控制路由，直接派发 researcher 任务。

增强功能：
- 支持基于前置探索结果动态生成章节
- 对于 list 类型查询，为每个发现的实体创建专门的章节
"""

from langchain_core.messages import get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command, Send

from src.prompts import load_prompt
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

from ..state import AgentState, DeepResearchConfig, DiscoveredItem, Section
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


def _generate_sections_from_discovered_items(
    discovered_items: list[DiscoveredItem],
    query_type: str,
    output_format: str,
    original_query: str,
) -> tuple[list[Section], str]:
    """
    根据前置探索的结果动态生成章节列表。

    增强方案：基于整体检索结果，为每个发现的实体生成专门的研究章节。

    返回: (sections, brief_text)
    """
    sections = []

    if not discovered_items:
        # 没有发现项目，返回空列表（会回退到普通规划）
        return [], ""

    # 按分类分组
    categories: dict[str, list[DiscoveredItem]] = {}
    for item in discovered_items:
        cat = item.category or "其他"
        if cat not in categories:
            categories[cat] = []
        categories[cat].append(item)

    # 1. 添加概述章节
    overview_section = Section(
        title="概述与现状",
        description=f"整体概述所有发现的选项，包括整体格局、主要分类、发展趋势。涵盖 {len(discovered_items)} 个选项，分属 {len(categories)} 个分类。",
        status="pending",
    )
    sections.append(overview_section)

    # 2. 为每个发现的实体生成专门章节
    # 按优先级排序：high -> medium -> low
    priority_order = {"high": 0, "medium": 1, "low": 2}

    for category, items in categories.items():
        # 按优先级排序
        sorted_items = sorted(
            items,
            key=lambda x: priority_order.get(getattr(x, "priority", "medium"), 1),
        )

        for item in sorted_items:
            section = Section(
                title=f"{item.name}",
                description=f"深入研究 {item.name}（{category}）: {item.brief}。需要获取：整体介绍、核心特性、应用场景、优缺点、相关链接（官网/GitHub/论文）。",
                status="pending",
            )
            sections.append(section)

    # 3. 添加对比总结章节
    comparison_section = Section(
        title="对比分析与选型建议",
        description=f"对比所有 {len(discovered_items)} 个选项的特点，从功能、性能、易用性、部署要求等维度进行对比分析，给出不同场景下的选型建议。",
        status="pending",
    )
    sections.append(comparison_section)

    # 构建研究简报文本
    sections_text = "\n".join(f"- **{s.title}**: {s.description}" for s in sections)
    categories_text = ", ".join(
        f"{cat}({len(items)}个)" for cat, items in categories.items()
    )

    brief_text = load_prompt(
        "deep_research/brief_from_discovery",
        original_query=original_query,
        total_items=len(discovered_items),
        categories_text=categories_text,
        query_type=query_type,
        output_format=output_format,
        sections_text=sections_text,
    )

    return sections, brief_text


async def plan_sections_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command:
    """
    从用户查询生成结构化研究简报和章节列表。

    使用 Command API 控制路由：
    - 生成/获取 sections 后，直接派发 researcher 任务（Send）
    - 如果已有 sections（review 循环回来），跳过重新生成，直接派发 pending 的章节

    增强方案：
    - 如果有 discovered_items（前置探索结果），基于前置探索结果动态生成章节
    - 每个发现的实体都会有专门的章节进行深入研究

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
        logger.info(
            "Brief skipped (review loop)",
            total_sections=len(existing_sections),
            pending_sections=len(pending_sections),
        )
        print(
            f"\n[Brief]: 跳过重新生成（已有 {len(existing_sections)} 个章节，"
            f"{len(pending_sections)} 个待研究）\n"
        )

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

    # === 增强方案：检查是否有前置探索的结果 ===
    discovered_items = get_state_value(state, "discovered_items", [])
    query_type = get_state_value(state, "query_type", "general")
    output_format = get_state_value(state, "output_format", "prose")
    original_query = get_state_value(state, "original_query", "")

    if discovered_items:
        # 基于发现结果动态生成章节
        logger.info(
            "Brief from discovered items",
            discovered_count=len(discovered_items),
        )
        print(f"\n[Brief]: 基于前置探索结果生成章节（发现 {len(discovered_items)} 个实体）")

        sections, brief_text = _generate_sections_from_discovered_items(
            discovered_items=discovered_items,
            query_type=query_type,
            output_format=output_format,
            original_query=original_query,
        )

        if sections:
            logger.info(
                "Brief sections generated (from discovery)",
                section_count=len(sections),
                section_titles=[s.title for s in sections],
            )
            print(f"  生成 {len(sections)} 个研究章节:")
            for s in sections:
                print(f"    - {s.title}")
            print()

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

            return Command(
                goto=sends,
                update={
                    "research_brief": brief_text,
                    "sections": sections,
                    "max_review_iterations": deep_config.max_review_iterations,
                },
            )

    # === 常规流程：使用 LLM 生成研究大纲 ===
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

    # 记录研究大纲
    logger.info(
        "Research brief generated",
        title=result.title,
        objective=result.objective,
        scope=result.scope,
        section_count=len(result.sections),
        section_titles=[s.title for s in result.sections],
    )
    # 打印研究大纲（终端输出）
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
    brief_text = load_prompt(
        "deep_research/brief_from_plan",
        title=result.title,
        objective=result.objective,
        scope=result.scope,
        sections_text=sections_text,
    )

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
            "query_type": query_type,
            "output_format": output_format,
        },
    )


# 保留旧名称作为别名以兼容
write_research_brief_node = plan_sections_node
