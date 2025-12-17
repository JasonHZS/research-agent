# Research Agent

A deep research agent built with LangGraph and LangChain, featuring MCP (Model Context Protocol) tools integration for comprehensive AI research capabilities.

## Features

- **ArXiv Search**: Search and retrieve academic papers from ArXiv
- **Hacker News Integration**: Get trending stories and discussions
- **Hugging Face Daily Papers**: Fetch daily featured AI/ML papers with titles and abstracts
- **Multi-LLM Support**: Works with Aliyun (qwen-max, kimi-k2-thinking), Anthropic Claude, and OpenAI GPT
- **Modular Architecture**: High cohesion, low coupling design for easy extension

## Architecture

```
src/
├── agent/
│   ├── __init__.py
│   └── research_agent.py    # Main agent implementation with LangGraph
├── config/
│   ├── __init__.py
│   └── mcp_config.py        # MCP server configurations
├── tools/
│   ├── __init__.py
│   └── hf_daily_papers.py   # Hugging Face daily papers tool
└── main.py                   # CLI entry point
```

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Node.js (for Hacker News MCP server)
- API key for Aliyun DashScope (default), Anthropic, or OpenAI

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

#### ArXiv MCP Server

```bash
# Install via uvx (recommended)
uvx arxiv-mcp-server

# Or install globally
pip install arxiv-mcp-server
```

#### Hacker News MCP Server

```bash
# Will be installed automatically via npx when the agent runs
# Or install globally:
npm install -g mcp-hn
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
```

## Usage

### Interactive Mode

```bash
# Run with default settings (Aliyun qwen-max)
uv run python -m src.main

# Use kimi-k2-thinking model
uv run python -m src.main -m kimi-k2-thinking

# Use Anthropic or OpenAI instead
uv run python -m src.main -p anthropic
uv run python -m src.main -p openai
```

### Single Query Mode

```bash
uv run python src/main.py -q "帮我深度总结一下 hacker news 和 huggingface 上今天的热门话题和论文"
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
        )
        print(result)

asyncio.run(main())
```

### Using Individual Tools

```python
from src.tools.hf_daily_papers import fetch_huggingface_daily_papers

# Fetch papers for a specific date
papers = fetch_huggingface_daily_papers("2025-12-15")
for paper in papers:
    print(f"Title: {paper['title']}")
    print(f"Abstract: {paper['abstract'][:200]}...")
    print()
```

## Available Tools

### Built-in Tools

| Tool | Description |
|------|-------------|
| `get_huggingface_papers_tool` | Fetches daily papers from Hugging Face with titles and abstracts |

### MCP Tools (via external servers)

| Server | Tools | Description |
|--------|-------|-------------|
| ArXiv MCP | `search_arxiv`, `get_paper` | Search and retrieve ArXiv papers |
| Hacker News MCP | `get_stories`, `get_comments` | Fetch HN stories and discussions |

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
2. Check that `uvx` is available for the ArXiv MCP server
3. Verify your PATH includes the necessary executables

### API Key Errors

1. Ensure your `.env` file exists and contains valid API keys
2. Check that `python-dotenv` is installed
3. Verify the API key has sufficient quota/credits

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [LangChain](https://langchain.com/) - LLM framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent graph framework
- [ArXiv MCP Server](https://github.com/blazickjp/arxiv-mcp-server) - ArXiv integration
- [mcp-hn](https://github.com/erithwik/mcp-hn) - Hacker News integration
- [Hugging Face](https://huggingface.co/) - Daily papers source
