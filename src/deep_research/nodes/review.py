"""
Review Node

评估研究覆盖度，决定是否需要继续研究或可以生成最终报告。
使用 Command API 控制路由。
"""

from typing import Literal

from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.prompts import load_prompt
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

from ..state import AgentState, DeepResearchConfig, Section
from ..structured_outputs import ReviewResult
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


async def review_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["plan_sections", "final_report"]]:
    """
    评估研究覆盖度。

    检查每个章节的内容是否充足，使用 Command API 决定下一步：
    - 如果信息充足或达到最大迭代次数：goto="final_report"
    - 如果有信息缺口且还有迭代次数：goto="plan_sections"（重新派发）

    返回：
    - Command 对象，包含路由决策和状态更新
    """
    deep_config = _get_config(config)

    llm = get_llm(deep_config.model_provider, deep_config.model_name)

    sections = get_state_value(state, "sections", [])
    original_query = get_state_value(state, "original_query", "")
    review_iterations = get_state_value(state, "review_iterations", 0)
    max_review_iterations = get_state_value(state, "max_review_iterations", 2)

    # 构建已收集信息的摘要
    sections_summary = []
    for s in sections:
        status_icon = "✅" if s.status == "completed" else "⏳"
        content_preview = s.content[:500] + "..." if len(s.content) > 500 else s.content
        sections_summary.append(
            f"### {status_icon} {s.title}\n"
            f"**状态**: {s.status}\n"
            f"**来源数**: {len(s.sources)}\n"
            f"**内容预览**:\n{content_preview}\n"
        )

    gathered_info = "\n\n".join(sections_summary)

    # 构建章节列表
    sections_outline = "\n".join(
        f"- **{s.title}**: {s.description}" for s in sections
    )

    # 加载 reflect 提示
    prompt_text = load_prompt(
        "deep_research/reflect",
        query=original_query,
        sections=sections_outline,
        gathered_info=gathered_info,
        iteration_count=review_iterations + 1,
        max_iterations=max_review_iterations,
    )

    try:
        llm_with_output = llm.with_structured_output(ReviewResult)
        result: ReviewResult = await llm_with_output.ainvoke(prompt_text)

        logger.info(
            "Review completed",
            score=result.overall_score,
            is_sufficient=result.is_sufficient,
            iteration=review_iterations + 1,
            max_iterations=max_review_iterations,
        )
        print(f"\n[Review]: 评分={result.overall_score}/10, 充足={result.is_sufficient}")
        print(f"  迭代: {review_iterations + 1}/{max_review_iterations}")

        # 如果信息充足或达到最大迭代，进入报告生成
        if result.is_sufficient or (review_iterations + 1) >= max_review_iterations:
            logger.info("Review decision: proceed to final report")
            print("  -> 进入最终报告生成\n")
            return Command(
                goto="final_report",
                update={"review_iterations": review_iterations + 1},
            )

        # 否则，将需要重新研究的章节标记为 pending
        sections_to_retry = set(result.sections_to_retry)
        updated_sections = []
        for s in sections:
            if s.title in sections_to_retry:
                # 重置为 pending
                updated_sections.append(
                    Section(
                        title=s.title,
                        description=s.description,
                        status="pending",
                        content="",  # 清空内容以重新研究
                        sources=[],
                    )
                )
            else:
                updated_sections.append(s)

        logger.info(
            "Review decision: retry sections",
            sections_to_retry=list(sections_to_retry),
        )
        print(f"  需要重新研究: {list(sections_to_retry)}")
        print("  -> 返回 plan_sections 重新派发\n")

        return Command(
            goto="plan_sections",
            update={
                "sections": updated_sections,
                "review_iterations": review_iterations + 1,
            },
        )

    except Exception as e:
        # 出错时直接继续到报告生成
        logger.warning(
            "Review evaluation error, proceeding to final report",
            error=str(e),
            error_type=type(e).__name__,
        )
        print(f"\n[Review]: 评估出错: {e}，直接生成报告\n")
        return Command(
            goto="final_report",
            update={"review_iterations": review_iterations + 1},
        )

