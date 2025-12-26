"""
Final Report Generation Node

从收集的 Section 内容生成综合研究报告。
"""

from langchain_core.messages import SystemMessage
from langchain_core.runnables import RunnableConfig

from src.prompts import load_prompt

from ..state import AgentState, DeepResearchConfig
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


async def final_report_node(
    state: AgentState,
    config: RunnableConfig,
) -> dict:
    """
    从所有章节内容生成最终研究报告。

    基于 Section 的内容和来源，生成结构化的最终报告。
    """
    deep_config = _get_config(config)

    llm = get_llm(deep_config.model_provider, deep_config.model_name)

    # 从 sections 构建研究内容
    sections = get_state_value(state, "sections", [])
    original_query = get_state_value(state, "original_query", "")
    research_brief = get_state_value(state, "research_brief", "")

    # 构建章节内容汇总
    sections_content = []
    all_sources = []

    for s in sections:
        section_text = f"## {s.title}\n\n{s.content}"
        if s.sources:
            section_text += f"\n\n**来源**: {', '.join(s.sources[:5])}"
            all_sources.extend(s.sources)
        sections_content.append(section_text)

    gathered_info = "\n\n---\n\n".join(sections_content)

    # 检查是否有内容
    has_content = any(s.content.strip() for s in sections)
    content_missing_msg = (
        "（未收集到任何研究内容，可能是上游代理未触发工具或模型响应为空。）"
        if not has_content
        else ""
    )

    # 加载报告生成提示
    prompt_text = load_prompt(
        "deep_research/final_report",
        query=original_query,
        research_brief=research_brief,
        gathered_info=gathered_info,
    )

    # token 限制的重试逻辑
    max_retries = 3
    current_info = gathered_info

    for attempt in range(max_retries):
        try:
            response = await llm.ainvoke([SystemMessage(content=prompt_text)])
            content = getattr(response, "content", "") or ""
            content = content.strip() if isinstance(content, str) else str(content)
            if content:
                return {"final_report": content}
            # 模型返回空内容时的兜底
            fallback = (
                f"未能生成完整报告{content_missing_msg}。"
                f"\n\n以下是研究简报供参考：\n{research_brief or original_query}"
            )
            return {"final_report": fallback}
        except Exception as e:
            error_str = str(e).lower()
            if "token" in error_str and attempt < max_retries - 1:
                # 重试时截断内容 10%
                truncate_len = int(len(current_info) * 0.9)
                current_info = current_info[:truncate_len]
                prompt_text = load_prompt(
                    "deep_research/final_report",
                    query=original_query,
                    research_brief=research_brief,
                    gathered_info=current_info,
                )
            else:
                fallback = (
                    f"生成报告时出错{content_missing_msg}：{e}\n\n"
                    f"以下是当前可用的简报或内容，供手动参考：\n"
                )
                if research_brief:
                    fallback += f"{research_brief}\n"
                if gathered_info:
                    fallback += f"\n内容片段：\n{gathered_info[:2000]}"
                return {"final_report": fallback}

    # 理论上不会走到这里，保留兜底
    return {
        "final_report": f"未能生成报告{content_missing_msg}。"
        f"\n\n参考简报：\n{research_brief or original_query}"
    }
