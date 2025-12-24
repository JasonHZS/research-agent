"""
Deep Research State Definition

This module defines the state schema for the Deep Research graph.
The state is passed between all nodes and accumulates research findings.
"""

import operator
from typing import Annotated, Optional

from langchain_core.messages import BaseMessage
from pydantic import BaseModel


class DeepResearchState(BaseModel):
    """
    State for the Deep Research graph.

    This state is passed between all nodes and accumulates research findings.
    """

    # Original user query
    original_query: str = ""
    # Clarified/refined research question
    clarified_query: str = ""
    # Whether intent has been clarified
    is_clarified: bool = False
    # Pending question for user (triggers human interaction)
    pending_question: Optional[str] = None
    # User's answer to clarification question
    user_answer: Optional[str] = None
    # Conversation history for clarification
    clarification_history: list[str] = []

    # Research plan sections
    sections: list[dict] = []
    # Current section being researched
    current_section_index: int = 0

    # Gathered information (summaries from reading)
    gathered_info: Annotated[list[str], operator.add] = []
    # Visited sources (for deduplication)
    visited_sources: Annotated[list[str], operator.add] = []

    # Iteration control
    iteration_count: int = 0
    max_iterations: int = 5
    # Whether evidence is sufficient
    is_sufficient: bool = False

    # Search queries for current iteration
    current_queries: list[str] = []
    # Raw search results (before reading)
    search_results: list[str] = []

    # Final report
    final_report: str = ""

    # Messages for tool calling
    messages: Annotated[list[BaseMessage], operator.add] = []

    class Config:
        arbitrary_types_allowed = True
