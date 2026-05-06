# Content Reader Subagent Testing Guide

## Overview

The script `tests/integration/test_content_reader.py` runs the **content reader** configuration (`create_content_reader_subagent()`) in isolation: one configured URL reader (Jina or Zyte, from `CONTENT_READER_TYPE`) plus `github_readme_tool`.

There is **no MCP** and no separate ArXiv tool in this subagent; ArXiv is used by the main research agent, not this standalone test harness.

## Prerequisites

- `.env` with LLM key (`ALIYUN_API_KEY`, `OPENAI_API_KEY`, or `OPENROUTER_API_KEY`)
- For **Jina** reader: `JINA_API_KEY`
- For **Zyte** reader: Zyte credentials per `env.example` / `src/config/settings.py`

## Usage

```bash
# Read a URL (default query wrapper)
uv run python tests/integration/test_content_reader.py --url "https://example.com"

# Custom instruction
uv run python tests/integration/test_content_reader.py --query "Summarize https://example.com in bullet points"

# Verbose (tool / agent debug from DeepAgents)
uv run python tests/integration/test_content_reader.py --url "https://example.com" -v

# Provider / model
uv run python tests/integration/test_content_reader.py --url "https://example.com" -p aliyun -m deepseek-v4-flash
uv run python tests/integration/test_content_reader.py --url "https://example.com" -m deepseek-v4-flash
```

## Options

| Flag | Description |
|------|-------------|
| `--url URL` | Wraps a standard “read and summarize this URL” prompt |
| `--query TEXT` | Sends your text directly to the subagent |
| `-p`, `--model-provider` | `aliyun` (default), `openai`, or `openrouter` |
| `-m`, `--model-name` | Optional model override |
| `-v`, `--verbose` | DeepAgents `debug=True` |

`--url` and `--query` are mutually required (exactly one).

## See also

- Full tool inventory: [agent_tools.md](agent_tools.md)
- Subagent definition: `src/agent/subagents/content_reader_agent.py`
