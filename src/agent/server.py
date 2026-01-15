"""
LangGraph Server Entry Point - Research Agent (React Pattern)

导出普通的 React 风格 research agent（基于 DeepAgents）。
与 deep_research 的区别：
- deep_research: 多阶段 supervisor-researcher 架构，适合复杂研究任务
- research_agent: 单 agent React 模式，适合简单问答和快速研究

使用方式:
    在 Agent Chat UI 中选择 Graph ID: research_agent
"""

import asyncio
from typing import Optional

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config.llm_config import get_model_settings
from src.config.mcp_config import get_single_server_config
from src.agent.research_agent import create_research_agent

# 加载环境变量
load_dotenv()

# 全局变量存储 MCP client（保持连接活跃）
_mcp_client: Optional[MultiServerMCPClient] = None


async def _load_mcp_tools() -> list:
    """异步加载 MCP tools。"""
    global _mcp_client

    try:
        config = get_single_server_config("hackernews")
        _mcp_client = MultiServerMCPClient({"hackernews": config})
        tools = await _mcp_client.get_tools()
        print(f"[Research Agent Server] Loaded {len(tools)} MCP tools")
        return tools
    except Exception as e:
        print(f"[Research Agent Server] Warning: Could not load MCP tools: {e}")
        return []


def _create_graph():
    """创建并返回 research agent graph。"""
    model_settings = get_model_settings()
    provider = model_settings["provider"]
    model_name = model_settings["model_name"]

    print(f"[Research Agent Server] Initializing...")
    print(f"[Research Agent Server] Provider: {provider}, Model: {model_name or 'default'}")

    # 同步执行异步 MCP 初始化
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            hn_mcp_tools = []
        else:
            hn_mcp_tools = loop.run_until_complete(_load_mcp_tools())
    except RuntimeError:
        hn_mcp_tools = asyncio.run(_load_mcp_tools())

    # 创建 agent（DeepAgents 返回的也是 CompiledStateGraph）
    agent = create_research_agent(
        hn_mcp_tools=hn_mcp_tools,
        model_provider=provider,
        model_name=model_name,
    )

    print("[Research Agent Server] Agent created successfully!")
    return agent


# LangGraph Server 读取这个变量
graph = _create_graph()
