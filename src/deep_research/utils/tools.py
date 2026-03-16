"""
Tool Assembly Utilities

组装 supervisor 和 researcher 代理的工具集。
"""

from src.config.settings import ReaderType, resolve_reader_type


def get_all_research_tools() -> list:
    """
    组装 researcher 代理的所有研究工具。

    包含：
    - 搜索工具 (ArXiv, HuggingFace, GitHub, Tavily)
    - 阅读工具 (Jina 或 Zyte，基于配置)
    - Hacker News 工具 (原生 API)

    Returns:
        所有可用研究工具的列表。
    """
    # 延迟导入以避免循环依赖
    from src.tools.arxiv_api import get_arxiv_paper_tool, search_arxiv_papers_tool
    from src.tools.github_search import github_readme_tool, github_search_tool
    from src.tools.hacker_news import hn_tools
    from src.tools.hf_blog import get_huggingface_blog_posts_tool
    from src.tools.hf_daily_papers import get_huggingface_papers_tool
    from src.tools.tavily_search import tavily_search_tool
    from src.tools.zyte_reader import get_zyte_article_list_tool

    # 核心搜索工具
    tools = [
        search_arxiv_papers_tool,
        get_arxiv_paper_tool,
        get_huggingface_papers_tool,
        get_huggingface_blog_posts_tool,
        get_zyte_article_list_tool,
        github_search_tool,
        github_readme_tool,
        tavily_search_tool,
        *hn_tools,
    ]

    # 根据配置添加阅读工具
    reader_type = resolve_reader_type()
    if reader_type == ReaderType.ZYTE:
        from src.tools.zyte_reader import get_zyte_reader_tool

        tools.append(get_zyte_reader_tool)
    else:
        from src.tools.jina_reader import get_jina_reader_tool

        tools.append(get_jina_reader_tool)

    return tools
