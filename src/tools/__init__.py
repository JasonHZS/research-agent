"""Tools module for the research agent."""

from src.tools.arxiv_adapter import (
    create_arxiv_analysis_prompt_tool,
    create_research_discovery_prompt_tool,
)
from src.tools.hf_daily_papers import (
    fetch_huggingface_daily_papers,
    get_huggingface_papers_tool,
)
from src.tools.jina_reader import (
    fetch_url_as_markdown,
    get_jina_reader_tool,
)

__all__ = [
    "create_arxiv_analysis_prompt_tool",
    "create_research_discovery_prompt_tool",
    "fetch_huggingface_daily_papers",
    "get_huggingface_papers_tool",
    "fetch_url_as_markdown",
    "get_jina_reader_tool",
]

