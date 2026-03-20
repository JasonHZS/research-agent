# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a deep research agent built with LangGraph and DeepAgents. Research uses **native LangChain tools** (HTTP/API clients): ArXiv, Hacker News (Firebase API), Hugging Face papers and blog, Tavily, GitHub, RSS (OPML), Zyte article list, and configurable URL readers (Jina or Zyte). See [docs/agent_tools.md](docs/agent_tools.md) for the full tool matrix.

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
python -m src.main --model kimi-k2.5  # Use Kimi model

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
   - Tools are the `main_tools` list in `create_research_agent()` (ArXiv, HF, GitHub, Tavily, RSS, Zyte article list, HN native tools, etc.)
   - Delegates long-form URL reading to the content reader sub-agent via the DeepAgents `task` tool
   - Maintains clean context window (receives summaries, not raw content)

2. **Content Reader Sub-agent** (`src/agent/subagents/content_reader_agent.py`)
   - Handles deep reading and summarization
   - Tools: configured URL reader (`get_jina_reader_tool` or `get_zyte_reader_tool` per `CONTENT_READER_TYPE`) and `github_readme_tool`
   - Returns structured summaries to main agent
   - Protects main agent from context bloat

**Tool lists**: Edited in code — `main_tools` in `create_research_agent()`, and `tools` in `create_content_reader_subagent()`. Inventory: [docs/agent_tools.md](docs/agent_tools.md).

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
   - Models: `qwen3.5-plus` (default), `qwen3-max`, `kimi-k2.5`, `glm-5`
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

Built-in tools should be added to:
- `src/tools/` - Tool implementation as LangChain tool
- Main agent: Import and add to `main_tools` list in `create_research_agent()`
- Sub-agent: Import and add to `tools` list in `create_content_reader_subagent()`

### RSS Feeds Tool

`list_rss_feeds_tool` / `fetch_rss_articles_tool` - reads ~90 HN popular blogs via OPML.
- OPML source: `src/config/hn-popular-blogs-2025.opml`
- Feeds are cached in-memory per process; reset via `src.tools.rss_feeds._feeds_cache = {}`
- `_MAX_ARTICLES = 100` global cap prevents context window overflow

### Testing Subagents Independently

Run the integration helper (content reader only):

```bash
uv run python tests/integration/test_content_reader.py --url "https://example.com"
uv run python tests/integration/test_content_reader.py --query "Summarize https://example.com" -v
uv run python tests/integration/test_content_reader.py --url "https://example.com" -p anthropic
```

See `docs/test_content_reader.md` for details.

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
│   ├── llm_factory.py              # LLM provider/model factory (create_llm())
│   ├── settings.py                 # Env-backed defaults (reader type, API ports, etc.)
│   └── hn-popular-blogs-2025.opml  # ~90 HN popular blogs for RSS tool
├── prompts/
│   ├── loader.py                   # Jinja2 template loader
│   └── templates/                  # Markdown prompt templates
│       └── trusted_sources.md      # Curated AI/ML sources list
├── tools/
│   ├── hf_daily_papers.py          # Hugging Face daily papers tool
│   ├── hf_blog.py                  # Hugging Face blog tool
│   ├── arxiv_api.py                # ArXiv search and paper fetch tools
│   ├── hacker_news.py              # Hacker News Firebase API tools
│   ├── jina_reader.py              # Jina URL reader (optional)
│   ├── zyte_reader.py              # Zyte URL reader / article list
│   ├── github_search.py            # GitHub search + README
│   ├── tavily_search.py            # Tavily web search
│   ├── rss_feeds.py                # RSS feed reader (OPML-backed)
│   └── arxiv_adapter.py            # ArXiv helpers (non-tool)
├── deep_research/                  # Deep research graph (LangGraph)
└── main.py                         # CLI entry point

tests/
├── integration/                    # Integration tests (require API keys/network)
└── test_rss_feeds.py               # Unit tests (mocked, no network)
scripts/                            # Utility scripts
```
