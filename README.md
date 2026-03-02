# Research Agent

A deep research agent built with LangGraph and LangChain, featuring MCP (Model Context Protocol) tools integration for comprehensive AI research capabilities.

## Features

- **Deep Research Mode**: Section-based parallel research with intent clarification, query analysis, entity discovery, review loops, and structured report generation
- **Smart Query Analysis**: Automatically identifies query types (list/comparison/deep_dive/general) and optimizes research strategy
- **Entity Discovery**: For "list" queries (e.g., "What are the best X?"), discovers all relevant entities before deep diving
- **ArXiv Search**: Search and retrieve academic papers using ArXiv's official API
- **Hacker News Integration**: Get trending stories and discussions via MCP
- **Hugging Face Daily Papers**: Fetch daily featured AI/ML papers with titles and abstracts
- **Hugging Face Blog**: Browse official and community blog posts with metadata
- **Multi-LLM Support**: Works with Aliyun (qwen3.5-plus, qwen-max, kimi-k2-thinking), Anthropic Claude, and OpenAI GPT
- **Thinking Mode**: Optional thinking mode for supported models (qwen3.5-plus, qwen-max, DeepSeek-v3.2, kimi-k2-thinking)
- **Modular Architecture**: High cohesion, low coupling design for easy extension
- **Clerk Authentication**: 使用 [Clerk](https://clerk.com/) 作为用户登录管理第三方服务，支持 Web UI 与 API 统一认证

## Two Research Modes

| Feature | Normal Mode | Deep Research Mode |
|---------|-------------|-------------------|
| Execution | Single-turn ReAct | Multi-turn state machine |
| Intent Clarification | None | Supported (skippable) |
| Query Analysis | None | Identifies query type (list/comparison/deep_dive/general) |
| Entity Discovery | None | Pre-research discovery for "list" queries |
| Research Planning | Implicit | Explicit section generation |
| Parallel Execution | None | Section-based parallel research |
| Review Mechanism | None | Review node evaluates evidence sufficiency |
| Context Management | Accumulates all messages | Researcher-level compression |
| Use Case | Simple queries, quick lookups | In-depth research, comprehensive reports |

## Architecture

### Deep Research Graph Flow

```mermaid
graph TB
    subgraph entry [Entry]
        Start([用户查询])
    end

    subgraph clarify_phase [意图澄清]
        Clarify[Clarify Node]
        UserInput([用户回答])
        Clarify -->|需要澄清| UserInput
        UserInput --> Clarify
    end

    subgraph analyze_phase [查询分析]
        Analyze[Analyze Node]
    end

    subgraph discovery_phase [前置探索]
        Discover[Discover Node]
    end

    subgraph parallel [并行研究]
        Plan[Plan Sections Node]
        R1[Researcher 1]
        R2[Researcher 2]
        RN[Researcher N]
        Aggregate[Aggregate Node]

        Plan -->|Command + Send| R1
        Plan -->|Command + Send| R2
        Plan -->|Command + Send| RN
        R1 --> Aggregate
        R2 --> Aggregate
        RN --> Aggregate
    end

    subgraph review_loop [评估闭环]
        Review[Review Node]
        Review -->|章节不足| Plan
    end

    subgraph output [Output]
        Report[Final Report Node]
        Final([研究报告])
    end

    Start --> Clarify
    Clarify --> Analyze
    Analyze -->|list 类型| Discover
    Analyze -->|其他类型| Plan
    Discover --> Plan
    Aggregate --> Review
    Review -->|证据充足| Report
    Report --> Final
```

## Prerequisites

- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (recommended) or pip
- Node.js (for Hacker News MCP server via npx)
- API key for Aliyun DashScope (default), Anthropic, or OpenAI
- Jina API key (for web content reading)
- Clerk 账号与密钥（使用 Web UI 时必需，见 [Clerk 用户认证](#clerk-用户认证)）

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

# Available models: qwen3.5-plus (default), qwen-max, kimi-k2-thinking

# Or use alternative providers:
# ANTHROPIC_API_KEY=your-anthropic-api-key
# OPENAI_API_KEY=your-openai-api-key

# Jina API Key (for web content reading)
# Get your key from: https://jina.ai/
JINA_API_KEY=your-jina-api-key

# Optional model defaults (CLI / API request has higher priority)
# MODEL_PROVIDER=aliyun
# MODEL_NAME=qwen3.5-plus
# ENABLE_THINKING=false

# Optional Deep Research defaults
# DEEP_RESEARCH_MAX_ITERATIONS=2
# DEEP_RESEARCH_MAX_CONCURRENT=5
# DEEP_RESEARCH_MAX_TOOL_CALLS=10
# DEEP_RESEARCH_ALLOW_CLARIFICATION=true
```

## Web UI & API

This project provides a Web UI and backend API service, allowing you to use the research agent through a web browser.

### Starting the Backend API

The backend uses FastAPI and provides RESTful API and streaming support.

```bash
# Start with uvicorn (development mode with hot reload)
ENV=development uv run uvicorn src.api.main:app --reload --port 8111

# Or use Python module approach
ENV=development uv run python -m src.api.main

# Use LangGraph CLI (recommended, supports LangGraph Studio)
langgraph dev
```

The API service runs on `http://localhost:8111` by default. You can configure it via environment variables:

```bash
API_HOST=0.0.0.0  # Default 0.0.0.0
API_PORT=8111     # Default 8111
```

### Production Deployment

For production environments, it is recommended to use `uv run` to ensure environment consistency and disable hot reload:

```bash
# Start with uvicorn (production mode)
# Logs will be written to logs/app.log in the project root (auto-created if not exists)
ENV=production uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8111

# Custom log path (optional)
ENV=production LOG_FILE=/path/to/your/app.log \
  uv run uvicorn src.api.main:app --host 0.0.0.0 --port 8111
```


### Starting the Frontend UI

The frontend is built with Next.js and located in the `web-ui/` directory.

```bash
# Navigate to the frontend directory
cd web-ui

# Install dependencies (first time only)
npm install

# Start the development server
npm run dev

# Or build for production
npm run build && cp -r .next/static .next/standalone/.next/static
npm run start:prod
```

The frontend development server runs on `http://localhost:3000` by default.

**Important**: The frontend needs to connect to the backend API, so make sure the backend service is running first.

### Clerk 用户认证

本项目的 Web UI 和 API 使用 [Clerk](https://clerk.com/) 作为用户登录管理服务，实现前后端统一的身份认证。

#### 获取 Clerk 密钥

1. 访问 [Clerk Dashboard](https://dashboard.clerk.com/)
2. 创建应用或选择现有应用
3. 在 **API Keys** 页面获取：
   - **Publishable Key**：用于前端（以 `pk_` 开头）
   - **Secret Key**：用于后端（以 `sk_` 开头）

#### 前端配置

在 `web-ui/` 目录下创建 `.env.local`（可参考 `web-ui/.env.local.example`）：

```bash
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=pk_test_xxxx
CLERK_SECRET_KEY=sk_test_xxxx
```

#### 后端配置

在项目根目录的 `.env` 中添加：

```bash
# Clerk Authentication (required for API protection)
CLERK_SECRET_KEY=sk_test_xxxx
# 可选：指定允许的前端域名（逗号分隔），默认包含 localhost:3000 等开发地址
# CLERK_AUTHORIZED_PARTIES=http://localhost:3000,https://your-production-domain.com
```

#### 部署说明

生产环境下，Next.js 使用 standalone 模式时需确保 Clerk 环境变量正确加载（例如通过 `dotenv-cli`）。详见 [部署网络问题排查 - Clerk secretKey 缺失](docs/deployment-network-troubleshooting.md#31-clerk-secretkey-缺失)。

## Usage

### Interactive Mode

```bash
# Run with default settings (Aliyun qwen3.5-plus)
uv run python -m src.main

# Use kimi-k2-thinking model
uv run python -m src.main --model kimi-k2-thinking

# Enable thinking mode (shows model's reasoning process)
uv run python -m src.main --enable-thinking
uv run python -m src.main --model kimi-k2-thinking --enable-thinking

# Use Anthropic or OpenAI instead
uv run python -m src.main -p anthropic
uv run python -m src.main -p openai
uv run python -m src.main -p openrouter --model openai/gpt-4o
```

### Single Query Mode

```bash
uv run python -m src.main -q "帮我深度总结一下 hacker news 和 huggingface 上今天的热门话题和论文的主要内容，并形成一篇详细的报告" -v

# With thinking mode enabled
uv run python -m src.main -q "分析最新的 LLM 论文趋势" --enable-thinking -v
```

### Deep Research Mode

Deep Research Mode uses a section-based parallel architecture for comprehensive research tasks. It includes intent clarification, structured section planning, parallel research execution, and iterative review.

```bash
# Interactive mode
uv run python -m src.main --deep-research

# With a query
uv run python -m src.main --deep-research -q "RAG 技术的最新进展有哪些？"

# Custom review iterations (default: 2)
uv run python -m src.main --deep-research --max-iterations 3 -q "对比 Llama 3 和 GPT-4 的技术架构"

# With verbose logging
uv run python -m src.main --deep-research -v

# Specify LLM provider
uv run python -m src.main --deep-research -p anthropic -q "Transformer 的注意力机制演进"

# Use a specific model
uv run python -m src.main --deep-research --model kimi-k2-thinking -q "LLM 推理优化技术"
```

Deep Research 参数优先级：`CLI 参数 > 环境变量 > 默认值`。  
默认值：`max_iterations=2`、`max_concurrent=5`、`max_tool_calls=10`。
约束范围：`max_iterations=1-5`、`max_concurrent=1-10`、`max_tool_calls=1-20`。

**Deep Research Flow:**
1. **Clarify** - Asks clarifying questions if the query is ambiguous (can be skipped)
2. **Analyze** - Identifies query type (list/comparison/deep_dive/general) and determines output format
3. **Discover** (list queries only) - Performs broad search to discover all relevant entities before deep research
4. **Plan Sections** - Generates 3-7 independent research sections based on query or discovered entities
5. **Parallel Research** - Each section is researched in parallel using available tools
6. **Review** - Evaluates evidence sufficiency across all sections
7. **Iterate or Report** - If gaps exist, re-research specific sections; otherwise generate final report

For detailed architecture documentation, see [`src/deep_research/README.md`](src/deep_research/README.md).

### Programmatic Usage

#### Normal Mode

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
            model_name="qwen3.5-plus", # or "qwen-max", "kimi-k2-thinking"
            enable_thinking=True,      # Enable thinking mode (optional)
        )
        print(result)

asyncio.run(main())
```

#### Deep Research Mode

```python
import asyncio
from src.deep_research import build_deep_research_graph, run_deep_research

async def main():
    # Build the deep research graph
    graph = build_deep_research_graph(
        hn_mcp_tools=None,  # Optional HN MCP tools
        model_provider="aliyun",
        model_name="qwen3.5-plus",
    )

    # Define clarification callback (optional)
    async def on_clarify(question: str) -> str:
        return input(f"Agent asks: {question}\nYour answer: ")

    # Configuration
    config = {
        "configurable": {
            "thread_id": "research-session-1",
            # Preferred keys (new naming)
            "max_tool_calls": 10,
            "max_iterations": 2,
            "model_provider": "aliyun",
            "model_name": "qwen3.5-plus",
        }
    }

    # Run deep research
    report = await run_deep_research(
        query="LLM 推理优化的最新技术",
        graph=graph,
        config=config,
        on_clarify_question=on_clarify,
    )
    print(report)

asyncio.run(main())
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

The Content Reader agent supports two reader tools, configured via environment variable:

```bash
# Options: zyte or jina
CONTENT_READER_TYPE=zyte
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

### Normal Mode (Quick Research)

```
📚 "What are the top papers on Hugging Face today about vision-language models?"

📚 "Search ArXiv for recent papers on reinforcement learning from human feedback"

📚 "What's trending on Hacker News about AI startups?"
```

### Deep Research Mode (Comprehensive Reports)

```
📖 "RAG 技术的最新进展有哪些？" (What are the latest advances in RAG?)

📖 "对比 Llama 3 和 GPT-4 的技术架构" (Compare Llama 3 and GPT-4 architecture)

📖 "Give me a comprehensive report on the latest advances in multimodal AI,
    including papers from ArXiv and Hugging Face, and relevant HN discussions"

📖 "Analyze the evolution of attention mechanisms in Transformers,
    covering sparse attention, linear attention, and recent innovations"
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

### Clerk 认证问题

1. 确保前后端均配置了正确的 Clerk 密钥（`NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`、`CLERK_SECRET_KEY`）
2. 生产环境 standalone 模式下，需通过 `dotenv-cli` 等方式加载 `.env.local`
3. 跨域访问时，检查 `CLERK_AUTHORIZED_PARTIES` 是否包含前端域名
4. 详见 [部署网络问题排查](docs/deployment-network-troubleshooting.md)

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [LangChain](https://langchain.com/) - LLM framework
- [LangGraph](https://langchain-ai.github.io/langgraph/) - Agent graph framework
- [ArXiv API](https://info.arxiv.org/help/api/index.html) - Academic paper search
- [mcp-hacker-news](https://github.com/erithwik/mcp-hn) - Hacker News integration
- [Hugging Face](https://huggingface.co/) - Daily papers and blog source
- [Jina AI](https://jina.ai/) - Web content reader
- [Clerk](https://clerk.com/) - 用户登录与身份认证
