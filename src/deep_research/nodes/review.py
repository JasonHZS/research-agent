"""
Review Node

评估研究覆盖度，决定是否需要继续研究或可以生成最终报告。
"""

from langchain_core.runnables import RunnableConfig

from src.prompts import load_prompt

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
) -> dict:
    """
    评估研究覆盖度。

    检查每个章节的内容是否充足，决定：
    - 如果信息充足或达到最大迭代次数：继续到 final_report
    - 如果有信息缺口且还有迭代次数：标记需要重新研究的章节为 pending

    返回：
    - sections: 更新后的章节列表（可能有些被重置为 pending）
    - review_iterations: 递增的计数
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

        # 如果信息充足或达到最大迭代，直接返回
        if result.is_sufficient or (review_iterations + 1) >= max_review_iterations:
            return {
                "review_iterations": review_iterations + 1,
            }

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

        return {
            "sections": updated_sections,
            "review_iterations": review_iterations + 1,
        }

    except Exception:
        # 出错时直接继续到报告生成
        return {
            "review_iterations": review_iterations + 1,
        }

