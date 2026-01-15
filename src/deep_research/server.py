"""
LangGraph Server Entry Point (with MCP Support)

导出编译后的 deep_research graph 供 LangGraph Server 使用。
支持 MCP tools（Hacker News 等）。

使用方式:
    1. 启动 server: langgraph dev
    2. 启动 Agent Chat UI: cd agent-chat-ui && pnpm dev
    3. 访问 http://localhost:3000
    4. 配置连接:
       - Deployment URL: http://localhost:2024
       - Graph ID: deep_research
    5. 开始对话

环境变量配置 (.env):
    - MODEL_PROVIDER: 模型提供商 (aliyun/anthropic/openai/openrouter)
    - MODEL_NAME: 具体模型名称
    - 各 API keys (ALIYUN_API_KEY, JINA_API_KEY, etc.)
"""

import asyncio
import os
from typing import Optional

from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config.llm_config import get_model_settings
from src.config.mcp_config import get_single_server_config
from src.deep_research.graph import build_deep_research_graph


# 全局变量存储 MCP client（保持连接活跃）
_mcp_client: Optional[MultiServerMCPClient] = None


async def _load_mcp_tools() -> list:
    """
    异步加载 MCP tools。

    Returns:
        MCP tools 列表，如果加载失败返回空列表。
    """
    global _mcp_client

    try:
        config = get_single_server_config("hackernews")
        _mcp_client = MultiServerMCPClient({"hackernews": config})
        tools = await _mcp_client.get_tools()
        print(f"[LangGraph Server] Loaded {len(tools)} MCP tools from hackernews")
        for tool in tools:
            print(f"  - {tool.name}")
        return tools
    except Exception as e:
        print(f"[LangGraph Server] Warning: Could not load MCP tools: {e}")
        print("[LangGraph Server] Continuing without MCP tools...")
        return []


def _create_graph():
    """
    创建并返回编译后的 deep_research graph。

    从环境变量读取模型配置，同步初始化 MCP tools。
    """
    # 从环境变量解析模型设置
    model_settings = get_model_settings()

    provider = model_settings["provider"]
    model_name = model_settings["model_name"]

    print(f"[LangGraph Server] Initializing deep_research graph...")
    print(f"[LangGraph Server] Provider: {provider}, Model: {model_name or 'default'}")

    # 同步执行异步 MCP 初始化
    # 使用 asyncio.run() 在模块加载时初始化 MCP tools
    try:
        # 检查是否已有事件循环
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # 如果已在运行的事件循环中，使用 nest_asyncio 或跳过
            print("[LangGraph Server] Event loop already running, skipping MCP init")
            hn_mcp_tools = []
        else:
            hn_mcp_tools = loop.run_until_complete(_load_mcp_tools())
    except RuntimeError:
        # 没有事件循环，创建新的
        hn_mcp_tools = asyncio.run(_load_mcp_tools())

    # 构建 graph
    compiled_graph = build_deep_research_graph(
        hn_mcp_tools=hn_mcp_tools,
        model_provider=provider,
        model_name=model_name,
    )

    print("[LangGraph Server] Graph compiled successfully!")
    return compiled_graph


# LangGraph Server 会读取这个变量
# 在模块加载时创建 graph 实例
graph = _create_graph()
