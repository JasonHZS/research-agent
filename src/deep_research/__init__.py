"""
Deep Research Module

This module provides a Deep Research mode using LangGraph StateGraph.
It implements a "Clarify -> Plan -> Retrieve -> Read -> Reflect" loop
that iteratively gathers information until evidence sufficiency is reached.
"""

from .state import DeepResearchState
from .deep_research_agent import build_deep_research_graph, run_deep_research

__all__ = [
    "DeepResearchState",
    "build_deep_research_graph",
    "run_deep_research",
]
