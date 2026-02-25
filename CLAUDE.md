# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a deep research agent built with LangGraph and DeepAgents, featuring MCP (Model Context Protocol) tools integration. The agent performs comprehensive AI research by searching ArXiv papers, fetching Hacker News discussions, and retrieving Hugging Face daily papers.

## Key Commands

### Environment Setup
```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .

# Install development dependencies
uv pip install -e ".[dev]"
```

### Running the Agent
```bash
# Interactive mode (default provider: Aliyun qwen3.5-plus)
python -m src.main

# Single query mode
python -m src.main --query "What are the latest LLM papers?"

# Use different providers
python -m src.main -p anthropic  # Use Claude
python -m src.main -p openai     # Use GPT
python -m src.main --model kimi-k2-thinking  # Use Kimi model

# Verbose mode (shows tool calls and agent steps)
python -m src.main -v
```

### Testing
```bash
# Run all tests
pytest

# Run unit tests only (no network required)
pytest tests/test_rss_feeds.py

# Run integration tests (require API keys / network)
pytest tests/integration/

# Run with verbose output
pytest -v
```

### Code Quality
```bash
# Check code style
ruff check src/

# Auto-format code
ruff format src/
```

## Architecture

### Two-Agent Architecture

The system uses a hierarchical agent design to manage context efficiently:

1. **Main Agent (Coordinator)** (`src/agent/research_agent.py`)
   - Handles discovery and planning using DeepAgents
   - Has access to search/discovery tools only:
     - Hugging Face papers list tool
     - ArXiv search tools (from MCP)
     - Hacker News get stories (from MCP)
   - Delegates content reading to sub-agent
   - Maintains clean context window (receives summaries, not raw content)

2. **Content Reader Sub-agent** (`src/agent/subagents/content_reader_agent.py`)
   - Handles deep reading and summarization
   - Has access to reading/consumption tools:
     - Jina Reader for web content
     - ArXiv read/download tools (from MCP)
   - Returns structured summaries to main agent
   - Protects main agent from context bloat

**Tool Distribution Logic**: The `get_main_agent_tools()` and `get_reader_agent_tools()` functions in `content_reader_agent.py` explicitly assign MCP tools to their respective agents using predefined whitelists.

### Multi-turn Conversation Support

The agent supports stateful conversations using LangGraph's persistence:

- **MemorySaver**: Persists conversation state across turns (in-memory, lost on exit)
- **InMemoryStore**: Enables file storage via `/memories/` path using `CompositeBackend`
- **thread_id**: Unique identifier for tracking conversation sessions

Key implementation in `src/main.py`:
```python
checkpointer = MemorySaver()  # For conversation state
store = InMemoryStore()       # For file persistence
thread_id = str(uuid.uuid4()) # Per-session identifier
```

### MCP Integration

MCP (Model Context Protocol) tools are loaded per-server from `src/config/mcp_config.py`:

- **ArXiv MCP**: Uses `uvx arxiv-mcp-server` (stdio transport)
- **Hacker News MCP**: Uses `npx -y mcp-hacker-news` (stdio transport)

Each MCP server is loaded independently in `src/main.py` via `_load_mcp_server_tools()`, allowing graceful degradation if a server fails to load.

### Prompt System

Prompts are managed via Jinja2 templates in `src/prompts/templates/`:

- `research_agent.md`: Main agent system prompt (static, no template variables)
- `content_reader.md`: Sub-agent system prompt (uses `{{ summary_format }}` variable)
- `summary.md`: Summary format template, embedded into content_reader.md

**Main Agent**: Edit `research_agent.md` directly to modify the prompt.

**Sub-agent**: Uses template composition - `summary.md` is loaded and injected into `content_reader.md`:
```python
from src.prompts import load_prompt
# Main agent: direct loading
system_prompt = load_prompt("research_agent")
# Sub-agent: template composition
summary_format = load_prompt("summary")
system_prompt = load_prompt("content_reader", summary_format=summary_format)
```

### LLM Provider Support

The agent supports three providers (configured in `src/agent/research_agent.py`):

1. **Aliyun (Default)**: Uses DashScope API with OpenAI-compatible endpoint
   - Models: `qwen3.5-plus` (default), `qwen-max`, `qwen3-max`, `kimi-k2-thinking`, `kimi-k2.5`, `deepseek-v3.2`, `glm-5`
   - Requires `ALIYUN_API_KEY` or `DASHSCOPE_API_KEY`
   - Custom base URL: `ALIYUN_API_BASE_URL` (optional)
   - Note: `enable_thinking=True` only works with `aliyun` provider

2. **Anthropic**: Native support
   - Default model: `claude-sonnet-4-20250514`
   - Requires `ANTHROPIC_API_KEY`

3. **OpenAI**: Native support
   - Default model: `gpt-4o`
   - Requires `OPENAI_API_KEY`

Model configuration is handled by `_get_model_config()` which creates appropriate ChatOpenAI instances for custom endpoints (Aliyun) or returns model names for native providers.

## Development Notes

### Environment Variables

Copy `env.example` to `.env` and configure:
```bash
# Primary API key (choose one based on provider)
ALIYUN_API_KEY=your-key           # For Aliyun/DashScope
ANTHROPIC_API_KEY=your-key        # For Claude
OPENAI_API_KEY=your-key           # For GPT

# Required for Jina Reader (web content fetching)
JINA_API_KEY=your-key

# Optional: Proxy settings (for restricted regions)
HTTP_PROXY=http://127.0.0.1:7897
HTTPS_PROXY=http://127.0.0.1:7897
```

### Adding New Tools

Built-in tools (non-MCP) should be added to:
- `src/tools/` - Tool implementation as LangChain tool
- Main agent: Import and add to `main_tools` list in `create_research_agent()`
- Sub-agent: Import and add to `tools` list in `create_content_reader_subagent()`

### RSS Feeds Tool

`list_rss_feeds_tool` / `fetch_rss_articles_tool` - reads ~90 HN popular blogs via OPML.
- OPML source: `src/config/hn-popular-blogs-2025.opml`
- Feeds are cached in-memory per process; reset via `src.tools.rss_feeds._feeds_cache = {}`
- `_MAX_ARTICLES = 100` global cap prevents context window overflow

### Adding New MCP Servers

1. Add server config to `get_mcp_config()` in `src/config/mcp_config.py`
2. Load tools in `initialize_mcp_tools()` in `src/main.py`
3. Pass tools to `create_research_agent()` as separate parameter
4. Filter tools in sub-agent if needed (search vs read tools)

### Testing Subagents Independently

The `scripts/test_content_reader.py` script allows testing the content reader subagent in isolation:

```bash
# Test reading a web page
python scripts/test_content_reader.py --url "https://example.com"

# Test reading an ArXiv paper
python scripts/test_content_reader.py --arxiv-id "2401.12345"

# Custom query with verbose output
python scripts/test_content_reader.py --query "Summarize this: https://example.com" -v

# Test with different providers
python scripts/test_content_reader.py --url "https://example.com" -p anthropic
```

This is useful for:
- Debugging subagent behavior without the full agent system
- Testing Jina Reader integration
- Verifying ArXiv MCP tool functionality
- Iterating on subagent prompts

See `docs/test_content_reader.md` for detailed usage.

### Debug Mode

Enable verbose mode with `-v` flag to see:
- Tool calls with arguments
- Agent reasoning steps
- Sub-agent invocations
- State transitions

This uses DeepAgents' built-in debug streaming (see `debug=verbose` in `_create_session_agent()`).

### Persistence Options

Current setup uses **in-memory persistence** (lost on exit):
- `MemorySaver` for conversation state
- `InMemoryStore` for file storage

For **persistent storage** across restarts:
- Use `SqliteSaver` or `PostgresSaver` instead of `MemorySaver`
- Use `SqliteStore` instead of `InMemoryStore`

See LangGraph documentation for setup details.

## Project Structure

```
src/
├── agent/
│   ├── research_agent.py           # Main agent creation and logic
│   └── subagents/
│       └── content_reader_agent.py # Sub-agent for content reading
├── config/
│   ├── mcp_config.py               # MCP server configurations
│   ├── llm_factory.py              # LLM provider/model factory (create_llm())
│   └── hn-popular-blogs-2025.opml  # ~90 HN popular blogs for RSS tool
├── prompts/
│   ├── loader.py                   # Jinja2 template loader
│   └── templates/                  # Markdown prompt templates
│       └── trusted_sources.md      # Curated AI/ML sources list
├── tools/
│   ├── hf_daily_papers.py          # Hugging Face daily papers tool
│   ├── jina_reader.py              # Jina AI web reader tool
│   ├── arxiv_adapter.py            # ArXiv helpers
│   └── rss_feeds.py                # RSS feed reader (OPML-backed)
├── deep_research/                  # Deep research graph (LangGraph)
└── main.py                         # CLI entry point

tests/
├── integration/                    # Integration tests (require API keys/network)
└── test_rss_feeds.py               # Unit tests (mocked, no network)
scripts/                            # Utility scripts
```
