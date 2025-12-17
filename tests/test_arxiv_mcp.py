"""
Test script for ArXiv MCP Server

This script tests the connection and functionality of the ArXiv MCP server.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv


async def test_arxiv_mcp():
    """Test the ArXiv MCP server connection and tools."""
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from src.config.mcp_config import get_mcp_config
    
    # Load environment variables (from .env if it exists)
    load_dotenv()

    print("=" * 60)
    print("Testing ArXiv MCP Server")
    print("=" * 60)
    print("\nConnecting to MCP server...")
    
    # Use the centralized config which now handles proxy pass-through
    mcp_config = get_mcp_config()
    
    # Filter to only run arxiv for this test
    arxiv_config = {"arxiv": mcp_config["arxiv"]}

    try:
        client = MultiServerMCPClient(arxiv_config)
        # Get available tools
        tools = await client.get_tools()
        
        print(f"\n✅ Successfully connected!")
        print(f"\n📦 Available tools ({len(tools)}):")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description[:80]}...")
        
        # Test one of the tools - search for papers
        print("\n" + "-" * 60)
        print("Testing: Searching for 'LLM Agents' papers...")
        print("-" * 60)
        
        # Find the tool for searching
        search_tool = None
        for tool in tools:
            if "search" in tool.name.lower() or "query" in tool.name.lower():
                search_tool = tool
                break
        
        if search_tool:
            print(f"\nUsing tool: {search_tool.name}")
            # Invoke the tool with a simple query
            # Note: The actual arguments depend on the tool definition, 
            # usually it's "query" or "search_query"
            try:
                # ArXiv tool usually expects a string or specific args. 
                # Let's try passing the query directly if it accepts a single arg string, 
                # or verify its schema. For now, assuming standard simple input.
                # Inspecting tool args schema might be better, but let's try a common dict.
                result = await search_tool.ainvoke({"query": "LLM Agents"})
                print(f"\n📄 Result (first 1000 chars):\n{str(result)[:1000]}...")
            except Exception as e:
                print(f"\n⚠️ Error invoking tool with {{'query': 'LLM Agents'}}: {e}")
                print("Trying with 'search_query' argument...")
                try:
                    result = await search_tool.ainvoke({"search_query": "LLM Agents"})
                    print(f"\n📄 Result (first 1000 chars):\n{str(result)[:1000]}...")
                except Exception as e2:
                     print(f"\n❌ Tool invocation failed: {e2}")

        else:
            print("\n⚠️ Could not find a search tool.")
            print("Available tools:", [t.name for t in tools])

        # Close the client if it has a close method
        if hasattr(client, 'close') and asyncio.iscoroutinefunction(client.close):
            await client.close()
        elif hasattr(client, 'close'):
            client.close()

    except Exception as e:
        print(f"\n❌ Error connecting to MCP server: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure 'uv' is installed: uv --version")
        print("2. Check your proxy settings in .env file")
        print("3. Try running manually: uvx arxiv-mcp-server")
        raise


if __name__ == "__main__":
    asyncio.run(test_arxiv_mcp())
