#!/usr/bin/env python3
"""
Inspect ArXiv MCP Prompts

This script connects to the ArXiv MCP server and prints the content
of the available prompts for inspection and evaluation.

Usage:
    python scripts/inspect_mcp_prompt.py [prompt_name] [--paper-id ID]

Examples:
    # Print the deep-paper-analysis prompt
    python scripts/inspect_mcp_prompt.py deep-paper-analysis --paper-id 2401.12345
    
    # Print the research-discovery prompt
    python scripts/inspect_mcp_prompt.py research-discovery --topic "LLM Agents"
"""

import asyncio
import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

from src.config.mcp_config import get_single_server_config


# Available prompts from arxiv-mcp-server
AVAILABLE_PROMPTS = {
    "deep-paper-analysis": {
        "description": "Detailed analysis of a specific paper",
        "required_args": ["paper_id"],
        "example": {"paper_id": "2401.12345"},
    },
    "research-discovery": {
        "description": "Discover relevant research on a topic",
        "required_args": ["topic"],
        "example": {"topic": "LLM Agents"},
    },
    "literature-synthesis": {
        "description": "Synthesize findings from multiple papers",
        "required_args": ["paper_ids"],
        "example": {"paper_ids": "2401.12345,2402.67890"},
    },
    "research-question": {
        "description": "Formulate research questions based on literature",
        "required_args": ["paper_ids", "topic"],
        "example": {"paper_ids": "2401.12345", "topic": "RAG"},
    },
}


async def inspect_prompt(
    prompt_name: str,
    arguments: dict,
) -> None:
    """
    Connect to ArXiv MCP server and print the specified prompt.
    
    Args:
        prompt_name: Name of the prompt to fetch.
        arguments: Arguments to pass to the prompt.
    """
    print("=" * 60)
    print(f"Inspecting ArXiv MCP Prompt: {prompt_name}")
    print("=" * 60)
    print(f"\nArguments: {arguments}\n")
    
    try:
        # Get ArXiv MCP config
        config = get_single_server_config("arxiv")
        
        print("Connecting to ArXiv MCP server...")
        client = MultiServerMCPClient({"arxiv": config})
        await client.__aenter__()
        
        print("Connected! Fetching prompt...\n")
        
        # Access the session
        session = client.sessions.get("arxiv")
        if not session:
            print("Error: ArXiv MCP session not available.")
            return
        
        # Call get_prompt
        result = await session.get_prompt(prompt_name, arguments=arguments)
        
        print("-" * 60)
        print("PROMPT CONTENT:")
        print("-" * 60)
        
        # Extract and print the content
        if hasattr(result, "messages") and result.messages:
            for i, msg in enumerate(result.messages):
                role = getattr(msg, "role", "unknown")
                print(f"\n[Message {i + 1}] Role: {role}")
                print("-" * 40)
                
                if hasattr(msg, "content"):
                    content = msg.content
                    if isinstance(content, str):
                        print(content)
                    elif hasattr(content, "text"):
                        print(content.text)
                    elif isinstance(content, list):
                        for item in content:
                            if hasattr(item, "text"):
                                print(item.text)
                            else:
                                print(item)
                    else:
                        print(content)
        else:
            print(f"Raw result: {result}")
        
        print("\n" + "=" * 60)
        
        # Cleanup
        await client.__aexit__(None, None, None)
        
    except Exception as e:
        print(f"\nError: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure 'uv' is installed: uv --version")
        print("2. Check your proxy settings in .env file")
        print("3. Try running manually: uvx arxiv-mcp-server")
        raise


def list_prompts() -> None:
    """Print all available prompts and their descriptions."""
    print("=" * 60)
    print("Available ArXiv MCP Prompts")
    print("=" * 60)
    
    for name, info in AVAILABLE_PROMPTS.items():
        print(f"\n{name}")
        print(f"  Description: {info['description']}")
        print(f"  Required args: {', '.join(info['required_args'])}")
        print(f"  Example: {info['example']}")
    
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Inspect ArXiv MCP prompts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    parser.add_argument(
        "prompt_name",
        nargs="?",
        default=None,
        help="Name of the prompt to inspect (e.g., 'deep-paper-analysis')",
    )
    parser.add_argument(
        "--paper-id",
        type=str,
        default="2401.12345",
        help="ArXiv paper ID for paper-related prompts",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default="LLM Agents",
        help="Research topic for topic-related prompts",
    )
    parser.add_argument(
        "--paper-ids",
        type=str,
        help="Comma-separated paper IDs for multi-paper prompts",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available prompts",
    )
    
    args = parser.parse_args()
    
    # Load environment variables
    load_dotenv()
    
    if args.list or args.prompt_name is None:
        list_prompts()
        if args.prompt_name is None:
            print("\nUsage: python scripts/inspect_mcp_prompt.py <prompt_name>")
            print("Example: python scripts/inspect_mcp_prompt.py deep-paper-analysis")
        return
    
    # Build arguments based on prompt type
    prompt_name = args.prompt_name
    
    if prompt_name not in AVAILABLE_PROMPTS:
        print(f"Unknown prompt: {prompt_name}")
        print(f"Available prompts: {', '.join(AVAILABLE_PROMPTS.keys())}")
        return
    
    prompt_info = AVAILABLE_PROMPTS[prompt_name]
    arguments = {}
    
    for arg_name in prompt_info["required_args"]:
        if arg_name == "paper_id":
            arguments["paper_id"] = args.paper_id
        elif arg_name == "topic":
            arguments["topic"] = args.topic
        elif arg_name == "paper_ids":
            arguments["paper_ids"] = args.paper_ids or "2401.12345,2402.67890"
    
    # Run the async inspection
    asyncio.run(inspect_prompt(prompt_name, arguments))


if __name__ == "__main__":
    main()
