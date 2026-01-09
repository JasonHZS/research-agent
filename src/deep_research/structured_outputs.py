"""
Structured Outputs for Deep Research

定义用于 Section-based 研究架构的 Pydantic 模型：
- SectionPlan: 研究大纲中的章节计划
- ResearchBrief: 完整的研究计划
- SectionContent: researcher 输出的章节内容
- ReviewResult: review 节点的评估结果
"""

from typing import Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 澄清工具
# ==============================================================================


class ClarifyWithUser(BaseModel):
    """
    用户澄清决策的结构化输出。

    用于 clarify_with_user 节点判断是否需要更多信息。
    """

    need_clarification: bool = Field(
        description="是否需要向用户询问更多信息以明确研究方向"
    )
    question: str = Field(
        description="如果需要澄清，这里是要问用户的问题（简洁具体）"
    )
    verification: str = Field(
        description="如果不需要澄清，这里是确认开始研究的消息，简要总结对用户需求的理解"
    )

    model_config = ConfigDict(extra="forbid")


# ==============================================================================
# 查询分析 (Analyze Node 输出)
# ==============================================================================


class QueryAnalysis(BaseModel):
    """
    查询分析结果。

    用于 analyze 节点识别查询类型和所需输出格式，
    决定是否需要前置探索（discover）阶段。
    """

    query_type: Literal["list", "comparison", "deep_dive", "general"] = Field(
        description="查询类型: list(有哪些/枚举), comparison(对比分析), deep_dive(深入研究), general(一般)"
    )
    output_format: Literal["table", "list", "prose"] = Field(
        description="期望输出格式: table(表格), list(清单), prose(文章)"
    )
    needs_discovery: bool = Field(
        description="是否需要先进行整体发现/枚举（用于 list 类型查询）"
    )
    discovery_target: str = Field(
        default="",
        description="如果需要发现，要发现的目标类型（如：某类模型、工具、框架）",
    )
    reasoning: str = Field(description="分析理由")


# ==============================================================================
# 前置探索输出 (Discover Node)
# ==============================================================================


class DiscoveredEntity(BaseModel):
    """
    前置探索阶段识别的单个实体。

    用于整体检索后提取的每个选项/模型/工具等。
    """

    name: str = Field(description="实体名称（如公司名、人名、模型名、工具名）")
    category: str = Field(default="", description="分类/类别")
    brief: str = Field(description="一句话描述")
    source: str = Field(default="", description="发现来源")
    priority: Literal["high", "medium", "low"] = Field(
        default="medium", description="研究优先级"
    )


class DiscoveryResult(BaseModel):
    """
    前置探索的完整结果。

    包含发现的所有实体和整体摘要。
    """

    entities: list[DiscoveredEntity] = Field(description="发现的实体列表")
    summary: str = Field(description="整体发现摘要（包含市场概况、主要分类等）")
    total_found: int = Field(description="总共发现的实体数量")
    categories: list[str] = Field(
        default_factory=list, description="发现的分类列表"
    )
    search_coverage: str = Field(
        default="", description="搜索覆盖说明（搜索了哪些来源）"
    )


# ==============================================================================
# 研究计划 (Plan Node 输出)
# ==============================================================================


class SectionPlan(BaseModel):
    """
    研究大纲中的单个章节计划。

    由 plan_sections 节点生成，定义每个章节的研究方向。
    """

    title: str = Field(description="章节标题")
    description: str = Field(description="该章节需要研究的内容和方向说明")


class ResearchBrief(BaseModel):
    """
    从用户查询生成的结构化研究简报。

    包含研究计划和章节划分。
    """

    title: str = Field(description="研究报告的标题")
    objective: str = Field(description="研究目标的一句话描述")
    sections: list[SectionPlan] = Field(
        description="研究章节列表（3-7 个），每个章节独立且可并行研究"
    )
    scope: str = Field(description="研究范围说明（包含什么、排除什么）")

    model_config = ConfigDict(extra="allow")


# ==============================================================================
# Researcher 输出 (Section Content)
# ==============================================================================


class SectionContent(BaseModel):
    """
    Researcher 为单个章节生成的内容。

    包含压缩后的研究发现和信息来源。
    """

    title: str = Field(description="章节标题（与输入的 Section.title 匹配）")
    content: str = Field(description="该章节的研究内容（Markdown 格式）")
    sources: list[str] = Field(description="信息来源列表（论文标题/URL）")
    key_findings: list[str] = Field(
        default_factory=list, description="关键发现列表（3-7 条）"
    )


class ResearchComplete(BaseModel):
    """
    Researcher 标记研究完成的工具参数。
    """

    summary: str = Field(description="研究完成的简要说明")
    confidence: Literal["high", "medium", "low"] = Field(
        default="medium", description="对研究充分性的信心程度"
    )


class ThinkTool(BaseModel):
    """
    战略思考工具，用于记录反思。

    Researcher 可使用此工具记录推理过程。
    不会产生外部动作，仅用于内部反思。
    """

    thought: str = Field(description="当前的思考内容，用于规划下一步或反思当前进展")


# ==============================================================================
# Review 输出
# ==============================================================================


class SectionCoverage(BaseModel):
    """单个章节的覆盖度评估"""

    title: str = Field(description="章节标题")
    status: Literal["sufficient", "partial", "missing"] = Field(
        description="覆盖状态"
    )
    notes: str = Field(default="", description="具体说明")


class ReviewResult(BaseModel):
    """
    Review 节点的评估结果。

    决定是否需要继续研究或可以生成最终报告。
    """

    is_sufficient: bool = Field(description="信息是否充足，可以生成报告")
    overall_score: int = Field(ge=1, le=10, description="整体评分 (1-10)")
    section_coverage: list[SectionCoverage] = Field(
        description="各章节覆盖度评估"
    )
    gaps: list[str] = Field(default_factory=list, description="缺失的关键信息点")
    sections_to_retry: list[str] = Field(
        default_factory=list, description="需要重新研究的章节标题列表"
    )
    reasoning: str = Field(description="整体评估理由")


# ==============================================================================
# 工具定义函数
# ==============================================================================


def get_researcher_tools(all_research_tools: list) -> list:
    """
    获取 researcher 代理的工具定义。

    包含所有搜索/阅读工具，以及：
    - research_complete: 标记章节研究完成
    - think: 战略思考
    """

    def research_complete(summary: str, confidence: str = "medium") -> str:
        """Signal that research on this section is complete."""
        return f"Section research complete: {summary}"

    def think(thought: str) -> str:
        """Record strategic thinking."""
        return f"Thought recorded: {thought}"

    completion_tools = [
        StructuredTool.from_function(
            func=research_complete,
            name="research_complete",
            description="标记当前章节的研究已完成",
            args_schema=ResearchComplete,
        ),
        StructuredTool.from_function(
            func=think,
            name="think",
            description="记录思考过程，用于规划检索策略",
            args_schema=ThinkTool,
        ),
    ]

    return list(all_research_tools) + completion_tools
