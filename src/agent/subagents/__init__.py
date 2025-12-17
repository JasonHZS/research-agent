"""Subagents module for the research agent."""

from src.agent.subagents.content_reader_agent import (
    create_content_reader_subagent,
    get_main_agent_tools,
    get_reader_agent_tools,
)

__all__ = [
    "create_content_reader_subagent",
    "get_main_agent_tools",
    "get_reader_agent_tools",
]
