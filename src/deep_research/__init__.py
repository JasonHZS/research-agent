"""
Deep Research Module

基于 Section 的深度研究架构，使用 LangGraph Send API 实现并行研究。

主要组件：
- build_deep_research_graph: 构建完整的深度研究图
- run_deep_research: 运行深度研究（支持人在环）
- AgentState: 主图状态
- Section: 报告章节模型
- ResearcherState: researcher 节点状态
"""

from .graph import build_deep_research_graph, run_deep_research
from .state import (
    AgentInputState,
    AgentOutputState,
    AgentState,
    DeepResearchConfig,
    ResearcherOutputState,
    ResearcherState,
    Section,
)

__all__ = [
    # 图构建
    "build_deep_research_graph",
    "run_deep_research",
    # 状态
    "AgentState",
    "AgentInputState",
    "AgentOutputState",
    "ResearcherState",
    "ResearcherOutputState",
    "DeepResearchConfig",
    "Section",
]
