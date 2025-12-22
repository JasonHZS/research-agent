"""Tools module for the research agent."""

from src.tools.arxiv_api import (
    fetch_arxiv_paper,
    get_arxiv_paper_tool,
    search_arxiv,
    search_arxiv_papers_tool,
)
from src.tools.hf_blog import (
    fetch_huggingface_blog_posts,
    get_huggingface_blog_posts_tool,
)
from src.tools.hf_daily_papers import (
    fetch_huggingface_daily_papers,
    get_huggingface_papers_tool,
)
from src.tools.jina_reader import (
    fetch_url_as_markdown,
    get_jina_reader_tool,
)
from src.tools.zyte_reader import (
    fetch_article_content,
    fetch_article_list,
    get_zyte_article_list_tool,
    get_zyte_reader_tool,
)

__all__ = [
    "fetch_arxiv_paper",
    "get_arxiv_paper_tool",
    "search_arxiv",
    "search_arxiv_papers_tool",
    "fetch_huggingface_daily_papers",
    "get_huggingface_papers_tool",
    "fetch_huggingface_blog_posts",
    "get_huggingface_blog_posts_tool",
    "fetch_url_as_markdown",
    "get_jina_reader_tool",
    "fetch_article_content",
    "fetch_article_list",
    "get_zyte_reader_tool",
    "get_zyte_article_list_tool",
]
