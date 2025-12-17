"""
Test script for Hacker News MCP Server

This script tests the connection and functionality of the Hacker News MCP server.
"""

import asyncio
import os
import sys
from dotenv import load_dotenv


async def test_hackernews_mcp():
    """Test the Hacker News MCP server connection and tools."""
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from src.config.mcp_config import get_mcp_config
    
    # Load environment variables (from .env if it exists)
    load_dotenv()

    print("=" * 60)
    print("Testing Hacker News MCP Server")
    print("=" * 60)
    print("\nConnecting to MCP server...")
    
    # Use the centralized config which now handles proxy pass-through
    mcp_config = get_mcp_config()
    
    # Filter to only run hackernews for this test
    hn_config = {"hackernews": mcp_config["hackernews"]}

    try:
        client = MultiServerMCPClient(hn_config)
        # Get available tools
        tools = await client.get_tools()
        
        print(f"\n✅ Successfully connected!")
        print(f"\n📦 Available tools ({len(tools)}):")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        
        # Test one of the tools - get top stories
        print("\n" + "-" * 60)
        print("Testing: Fetching top Hacker News stories...")
        print("-" * 60)
        
        # Find the tool for getting top stories
        get_stories_tool = None
        for tool in tools:
            if "top" in tool.name.lower() or "stories" in tool.name.lower():
                get_stories_tool = tool
                break
        
        if get_stories_tool:
            print(f"\nUsing tool: {get_stories_tool.name}")
            # Invoke the tool with num_stories parameter
            result = await get_stories_tool.ainvoke({"num_stories": 5})
            print(f"\n📰 Result:\n{str(result)}")
        else:
            print("\n⚠️ Could not find a tool for getting stories.")
            print("Available tools:", [t.name for t in tools])

        # Test another tool - get best stories
        print("\n" + "-" * 60)
        print("Testing: Fetching best Hacker News stories...")
        print("-" * 60)

        # Find the tool for getting best stories
        get_best_stories_tool = None
        for tool in tools:
            if "best" in tool.name.lower() and "stories" in tool.name.lower():
                get_best_stories_tool = tool
                break
        
        if get_best_stories_tool:
            print(f"\nUsing tool: {get_best_stories_tool.name}")
            # Invoke the tool with num_stories parameter
            result = await get_best_stories_tool.ainvoke({"num_stories": 5})
            print(f"\n📰 Result:\n{str(result)}")
        else:
            print("\n⚠️ Could not find tool for getting best stories.")

        # Close the client if it has a close method
        if hasattr(client, 'close') and asyncio.iscoroutinefunction(client.close):
            await client.close()
        elif hasattr(client, 'close'):
            client.close()

    except Exception as e:
        print(f"\n❌ Error connecting to MCP server: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure Node.js and npm are installed: node --version")
        print("2. Check your proxy settings in .env file")
        print("3. Try running manually: npx -y mcp-hacker-news")
        raise


if __name__ == "__main__":
    asyncio.run(test_hackernews_mcp())
