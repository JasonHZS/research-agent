# Research Agent

A deep research agent built with LangGraph and LangChain, featuring MCP (Model Context Protocol) tools integration for comprehensive AI research capabilities.

## Features

- **ArXiv Search**: Search and retrieve academic papers using ArXiv's official API
- **Hacker News Integration**: Get trending stories and discussions via MCP
- **Hugging Face Daily Papers**: Fetch daily featured AI/ML papers with titles and abstracts
- **Hugging Face Blog**: Browse official and community blog posts with metadata
- **Multi-LLM Support**: Works with Aliyun (qwen-max, kimi-k2-thinking), Anthropic Claude, and OpenAI GPT
- **Thinking Mode**: Optional thinking mode for supported models (qwen-max, DeepSeek-v3.2, kimi-k2-thinking)
- **Modular Architecture**: High cohesion, low coupling design for easy extension

## Architecture

```
src/
├── agent/
│   ├── __init__.py
│   ├── research_agent.py         # Main agent implementation with LangGraph
│   └── subagents/
│       └── content_reader_agent.py  # Sub-agent for content reading
├── config/
│   ├── __init__.py
│   ├── mcp_config.py             # MCP server configurations
│   └── reader_config.py          # Content reader tool configuration
├── prompts/
│   ├── loader.py                 # Jinja2 template loader
│   └── templates/                # Markdown prompt templates
├── tools/
│   ├── __init__.py
│   ├── arxiv_api.py              # ArXiv API search and fetch tools
│   ├── hf_blog.py                # Hugging Face blog listing tool
│   ├── hf_daily_papers.py        # Hugging Face daily papers tool
│   ├── jina_reader.py            # Jina AI web reader tool
│   └── zyte_reader.py            # Zyte API article extraction tool
└── main.py                       # CLI entry point
```

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Node.js (for Hacker News MCP server via npx)
- API key for Aliyun DashScope (default), Anthropic, or OpenAI
- Jina API key (for web content reading)

## Installation

### 1. Clone the repository

```bash
git clone <repository-url>
cd research-agent
```

### 2. Set up the environment with uv

```bash
# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
```

### 3. Install MCP Servers

#### Hacker News MCP Server

```bash
# Will be installed automatically via npx when the agent runs
# Or install globally:
npm install -g mcp-hacker-news
```

### 4. Configure Environment Variables

Create a `.env` file in the project root:

```bash
cp env.example .env
```

Edit `.env` and add your API keys:

```bash
# Aliyun DashScope (Default)
# Get your key from: https://dashscope.console.aliyun.com/
ALIYUN_API_KEY=your-aliyun-dashscope-api-key

# Available models: qwen-max (default), kimi-k2-thinking

# Or use alternative providers:
# ANTHROPIC_API_KEY=your-anthropic-api-key
# OPENAI_API_KEY=your-openai-api-key

# Jina API Key (for web content reading)
# Get your key from: https://jina.ai/
JINA_API_KEY=your-jina-api-key
```

## Usage

### Interactive Mode

```bash
# Run with default settings (Aliyun qwen-max)
uv run python -m src.main

# Use kimi-k2-thinking model
uv run python -m src.main --model kimi-k2-thinking

# Enable thinking mode (shows model's reasoning process)
uv run python -m src.main --enable-thinking
uv run python -m src.main --model kimi-k2-thinking --enable-thinking

# Use Anthropic or OpenAI instead
uv run python -m src.main -p anthropic
uv run python -m src.main -p openai
```

### Single Query Mode

```bash
uv run python -m src.main -q "帮我深度总结一下 hacker news 和 huggingface 上今天的热门话题和论文的主要内容，并形成一篇详细的报告" -v

# With thinking mode enabled
uv run python -m src.main -q "分析最新的 LLM 论文趋势" --enable-thinking -v
```

### Programmatic Usage

```python
import asyncio
from src.agent.research_agent import run_research
from src.config.mcp_config import get_mcp_config
from langchain_mcp_adapters.client import MultiServerMCPClient

async def main():
    # Initialize MCP tools
    mcp_config = get_mcp_config()
    async with MultiServerMCPClient(mcp_config) as client:
        tools = await client.get_tools()
        
        # Run research with Aliyun (default)
        result = await run_research(
            query="Summarize today's Hugging Face papers on transformers",
            mcp_tools=tools,
            model_provider="aliyun",  # or "anthropic", "openai"
            model_name="qwen-max",     # or "kimi-k2-thinking"
            enable_thinking=True,      # Enable thinking mode (optional)
        )
        print(result)

asyncio.run(main())
```

### Using Individual Tools

```python
from src.tools.hf_daily_papers import fetch_huggingface_daily_papers
from src.tools.hf_blog import fetch_huggingface_blog_posts
from src.tools.arxiv_api import search_arxiv, fetch_arxiv_paper

# Fetch Hugging Face daily papers for a specific date
papers = fetch_huggingface_daily_papers("2025-12-15")
for paper in papers:
    print(f"Title: {paper['title']}")
    print(f"Abstract: {paper['abstract'][:200]}...")

# Fetch Hugging Face blog posts
blog_posts = fetch_huggingface_blog_posts(limit=10)
for post in blog_posts:
    print(f"{post['title']} - {post['date']} ({post['upvotes']} upvotes)")

# Search ArXiv papers
results = search_arxiv("LLM agents", max_results=5, sort_by="submittedDate")
for paper in results:
    print(f"{paper['title']} [{paper['arxiv_id']}]")

# Fetch a specific ArXiv paper
paper = fetch_arxiv_paper("2402.02716")
print(f"Title: {paper['title']}")
print(f"Authors: {', '.join(paper['authors'][:3])}")
```

## Available Tools

### Built-in Tools

| Tool | Description |
|------|-------------|
| `search_arxiv_papers_tool` | Search ArXiv papers using official API with query syntax support |
| `get_arxiv_paper_tool` | Fetch detailed metadata for a specific ArXiv paper by ID |
| `get_huggingface_papers_tool` | Fetches daily papers from Hugging Face with titles and abstracts |
| `get_huggingface_blog_posts_tool` | Lists Hugging Face blog posts with title, date, upvotes, and URL |
| `get_jina_reader_tool` | Reads and extracts content from web URLs as markdown |
| `get_zyte_reader_tool` | Extracts structured article content via Zyte API |

### Content Reader Configuration

The Content Reader agent supports two reader tools. Configure in `src/config/reader_config.py`:

```python
# Options: ReaderType.JINA or ReaderType.ZYTE
READER_TYPE: ReaderType = ReaderType.ZYTE
```

| Reader | Description | Cost |
|--------|-------------|------|
| Jina | Converts web pages to markdown | Free |
| Zyte | Extracts structured article content (title, author, body) | Paid |

### MCP Tools (via external servers)

| Server | Tools | Description |
|--------|-------|-------------|
| Hacker News MCP | `getTopStories`, `getBestStories`, `getNewStories`, etc. | Fetch HN stories and discussions |

## Example Queries

```
📚 "What are the top papers on Hugging Face today about vision-language models?"

📚 "Search ArXiv for recent papers on reinforcement learning from human feedback"

📚 "What's trending on Hacker News about AI startups?"

📚 "Give me a comprehensive report on the latest advances in multimodal AI, 
    including papers from ArXiv and Hugging Face, and relevant HN discussions"
```

## Development

### Running Tests

```bash
uv pip install -e ".[dev]"
pytest
```

### Code Formatting

```bash
ruff check src/
ruff format src/
```

## Troubleshooting

### MCP Tools Not Loading

1. Ensure Node.js is installed for the Hacker News MCP server
2. Check that `npx` is available in your PATH
3. Verify your PATH includes the necessary executables

### API Key Errors

1. Ensure your `.env` file exists and contains valid API keys
2. Check that `python-dotenv` is installed
3. Verify the API key has sufficient quota/credits
4. For Jina Reader, ensure `JINA_API_KEY` is set

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [LangChain](https://langchain.com/) - LLM framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent graph framework
- [ArXiv API](https://info.arxiv.org/help/api/index.html) - Academic paper search
- [mcp-hacker-news](https://github.com/erithwik/mcp-hn) - Hacker News integration
- [Hugging Face](https://huggingface.co/) - Daily papers and blog source
- [Jina AI](https://jina.ai/) - Web content reader
