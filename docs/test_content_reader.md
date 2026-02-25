# Content Reader Subagent Testing Guide

## Overview

The `scripts/test_content_reader.py` script allows you to test the content reader subagent independently without running the full research agent system.

## Features

- Test web page reading using Jina Reader
- Test ArXiv paper reading using MCP tools
- Support for multiple LLM providers (Aliyun, Anthropic, OpenAI)
- Verbose mode to see tool calls and agent reasoning
- Optional MCP tools loading

## Usage Examples

### 1. Read a Web Page

```bash
python tests/test_content_reader.py --url "https://lilianweng.github.io/posts/2023-06-23-agent/"
```

### 2. Read an ArXiv Paper

```bash
python scripts/test_content_reader.py --arxiv-id "2401.12345"
```

### 3. Custom Query

```bash
python scripts/test_content_reader.py --query "Read and summarize https://example.com, focusing on the technical implementation"
```

### 4. Use Different LLM Providers

```bash
# Use Anthropic Claude
python scripts/test_content_reader.py --url "https://example.com" -p anthropic

# Use OpenAI GPT
python scripts/test_content_reader.py --url "https://example.com" -p openai

# Use specific model
python scripts/test_content_reader.py --url "https://example.com" --model kimi-k2-thinking
```

### 5. Verbose Mode (See Tool Calls)

```bash
python scripts/test_content_reader.py --url "https://example.com" -v
```

### 6. Disable MCP Tools

```bash
# Test with only Jina Reader (no ArXiv MCP)
python scripts/test_content_reader.py --url "https://example.com" --no-arxiv
```

## Prerequisites

1. **Environment Variables**: Ensure your `.env` file is configured with:
   - `JINA_API_KEY` (required for web reading)
   - LLM provider API key (`ALIYUN_API_KEY`, `ANTHROPIC_API_KEY`, or `OPENAI_API_KEY`)

2. **MCP Tools** (optional):
   - ArXiv MCP: Requires `uvx` to be installed
   - Hacker News MCP: Requires Node.js and `npx`

## How It Works

1. **Tool Loading**: Optionally loads ArXiv and/or Hacker News MCP tools
2. **Subagent Creation**: Uses `create_content_reader_subagent()` to build the configuration
3. **Agent Instantiation**: Creates a standalone agent with `create_deep_agent()`
4. **Query Execution**: Sends your query to the agent and displays the result

## Common Test Scenarios

### Test Jina Reader Only

```bash
# Disable all MCP tools to test only Jina Reader
python scripts/test_content_reader.py \
  --url "https://example.com" \
  --no-arxiv \
  -v
```

### Test ArXiv Paper Reading

```bash
# Read an ArXiv paper using MCP tools
python scripts/test_content_reader.py \
  --arxiv-id "2310.06825" \
  -v
```

### Test with Custom Instructions

```bash
python scripts/test_content_reader.py \
  --query "Read https://example.com and extract only the key technical insights in bullet points" \
  -v
```

## Troubleshooting

### Jina Reader Errors
- Ensure `JINA_API_KEY` is set in `.env`
- Check that the URL is accessible

### ArXiv MCP Errors
- Verify `uvx` is installed: `uvx --version`
- Test the MCP server manually: `uvx arxiv-mcp-server`
- Check proxy settings in `.env` if behind a firewall

### Model Errors
- Verify the correct API key is set for your provider
- Check that the model name is valid for your provider

## Script Options

```
usage: test_content_reader.py [-h] (--url URL | --arxiv-id ARXIV_ID | --query QUERY)
                              [-p {aliyun,anthropic,openai}] [-m MODEL_NAME]
                              [--no-arxiv] [--enable-hn] [-v]

Test the content reader subagent independently

optional arguments:
  -h, --help            show this help message and exit
  --url URL             URL to read and summarize
  --arxiv-id ARXIV_ID   ArXiv paper ID to read (e.g., '2401.12345')
  --query QUERY         Custom query to send to the content reader
  -p {aliyun,anthropic,openai}, --model-provider {aliyun,anthropic,openai}
                        LLM provider to use (default: aliyun)
  -m MODEL_NAME, --model-name MODEL_NAME
                        Model name (e.g., 'qwen3.5-plus', 'kimi-k2-thinking')
  --no-arxiv            Disable ArXiv MCP tools
  --enable-hn           Enable Hacker News MCP tools (disabled by default)
  -v, --verbose         Enable verbose mode (shows tool calls and agent steps)
```
