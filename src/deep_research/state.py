"""
Deep Research State Definitions

定义基于 Section 的研究架构状态模式：
- Section: 报告章节的结构化表示
- AgentState: 主图状态
- ResearcherState: researcher 节点状态 (通过 Send API 接收)
- 输出状态用于图接口
"""

import operator
from typing import Annotated, Literal, Optional

from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ==============================================================================
# Section 模型
# ==============================================================================


class Section(BaseModel):
    """
    报告的单个章节。

    每个 Section 代表研究报告中的一个独立部分，
    由专门的 Researcher 负责研究和填充内容。
    """

    title: str = Field(description="章节标题")
    description: str = Field(description="该章节的研究指导/描述")
    status: Literal["pending", "researching", "completed"] = Field(
        default="pending", description="章节状态"
    )
    content: str = Field(default="", description="研究内容（由 researcher 填充）")
    sources: list[str] = Field(default_factory=list, description="信息来源列表")


# ==============================================================================
# 前置探索模型
# ==============================================================================


class DiscoveredItem(BaseModel):
    """
    整体检索阶段发现的单个实体/项目。

    用于 list 类型查询，记录发现的每个选项/实体。
    """

    name: str = Field(description="实体名称（如模型名、项目名）")
    category: str = Field(default="", description="分类/类别")
    brief: str = Field(default="", description="简要描述")
    source: str = Field(default="", description="发现来源")
    urls: list[str] = Field(default_factory=list, description="相关链接（GitHub/官网/论文）")


def section_reducer(
    existing: list[Section], updates: list[Section]
) -> list[Section]:
    """
    Section 列表的自定义 reducer。
    LangGraph 的状态字段默认使用替换策略（新值覆盖旧值）。但 sections 是一个列表，需要增量更新

    根据 title 匹配并合并更新：
    - 如果 title 匹配，用新的 Section 替换旧的
    - 如果是新 title，追加到列表
    """
    if not existing:
        return updates

    result = list(existing)
    existing_titles = {s.title: i for i, s in enumerate(result)}

    for update in updates:
        if update.title in existing_titles:
            # 替换现有 section
            result[existing_titles[update.title]] = update
        else:
            # 追加新 section
            result.append(update)
            existing_titles[update.title] = len(result) - 1

    return result


# ==============================================================================
# 输入/输出状态类型 (TypedDict 用于图接口)
# ==============================================================================


class AgentInputState(TypedDict):
    """主图的输入状态 - 用户提供的内容"""

    messages: list[AnyMessage]


class AgentOutputState(TypedDict):
    """主图的输出状态 - 返回给用户的内容"""

    original_query: str
    messages: list[AnyMessage]
    query_type: str
    output_format: str
    discovered_items: list[DiscoveredItem]
    research_brief: str
    sections: list[Section]
    final_report: str


# ==============================================================================
# 主图状态
# ==============================================================================


class AgentState(MessagesState):
    """
    深度研究主图的顶层状态。

    继承 MessagesState 提供：
    - messages: Annotated[list[AnyMessage], add_messages]

    增强功能：
    - 支持"前置探索"：先整体检索发现实体，再针对每个实体深入研究
    - 查询类型识别：list/comparison/deep_dive/general
    """

    # 用户交互（澄清问题/确认消息通过 messages 传递）
    original_query: str = ""

    # === 查询分析 ===
    # 查询类型: list (有哪些) / comparison (对比) / deep_dive (深入) / general (一般)
    query_type: Literal["list", "comparison", "deep_dive", "general"] = "general"
    # 输出格式: table (表格) / list (清单) / prose (文章)
    output_format: Literal["table", "list", "prose"] = "prose"

    # === 前置探索（整体检索）===
    # 发现的实体列表（用于 list 类型查询）
    discovered_items: list[DiscoveredItem] = []
    # 前置探索是否完成
    discovery_complete: bool = False
    # 整体检索的原始结果（用于生成章节）
    discovery_summary: str = ""

    # 研究简报 (澄清后生成)
    research_brief: str = ""

    # 章节列表
    sections: Annotated[list[Section], section_reducer] = []

    # Review 迭代控制
    review_iterations: int = 0
    max_review_iterations: int = 2

    # 最终输出
    final_report: str = ""


# ==============================================================================
# Researcher 节点状态 (通过 Send API 接收)
# ==============================================================================


class ResearcherState(MessagesState):
    """
    单个 researcher 实例的状态。

    通过 Send API 接收，每个 researcher 专注于一个 Section。
    """

    # 研究任务 - 从 Send 接收
    section: Section = Field(default_factory=lambda: Section(title="", description=""))  # 工厂函数确保每个实例获得独立的 Section 对象
    research_brief: str = ""  # 提供上下文

    # researcher 的工具调用消息
    researcher_messages: Annotated[list[AnyMessage], operator.add] = []

    # 迭代跟踪
    tool_call_iterations: int = 0
    max_tool_calls: int = 20

    # 完成标志
    is_complete: bool = False


class ResearcherOutputState(TypedDict):
    """researcher 返回给主图的输出状态"""

    sections: list[Section]  # 更新后的 section (status=completed, content 已填充)


# ==============================================================================
# 配置状态 (通过 RunnableConfig 注入)
# ==============================================================================


class DeepResearchConfig(BaseModel):
    """
    深度研究执行的配置。

    在节点执行期间从 RunnableConfig 中获取。
    """

    # 并发控制
    max_tool_calls_per_researcher: int = Field(default=10, ge=1, le=20)
    max_review_iterations: int = Field(default=2, ge=1, le=5)

    # Token 限制
    max_context_tokens: int = Field(default=100000)
    compression_target_tokens: int = Field(default=10000)

    # 人机交互
    allow_clarification: bool = Field(default=True)

    # 模型设置 (运行时解析)
    model_provider: str = "aliyun"
    model_name: Optional[str] = "qwen-max"
    enable_thinking: bool = False

    # 调试/显示
    verbose: bool = Field(default=False, description="是否打印工具调用信息")
