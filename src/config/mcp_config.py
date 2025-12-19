"""
MCP (Model Context Protocol) Configuration

This module provides configuration for connecting to various MCP servers
including Hacker News.
"""

import os
from typing import Any


def get_mcp_env() -> dict[str, str]:
    """
    Get common environment variables to pass to MCP servers.
    Specifically passes through PATH and Proxy configurations.
    """
    env = {
        "PATH": os.environ.get("PATH", ""),
        "NODE_PATH": os.environ.get("NODE_PATH", ""),
    }
    
    # Pass through proxy settings if they exist
    proxy_vars = [
        "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY",
        "http_proxy", "https_proxy", "all_proxy", "no_proxy"
    ]
    
    for var in proxy_vars:
        if val := os.environ.get(var):
            env[var] = val
            
    return env


def get_mcp_config() -> dict[str, dict[str, Any]]:
    """
    Get the MCP server configuration for all integrated services.

    The configuration supports both stdio (subprocess) and SSE (HTTP) transports.

    Returns:
        Dictionary mapping server names to their connection configurations.
    """
    common_env = get_mcp_env()
    
    config = {
        # Hacker News MCP Server - https://github.com/erithwik/mcp-hn
        # Provides tools for fetching HN stories and comments
        "hackernews": {
            "transport": "stdio",
            "command": "npx",
            "args": ["-y", "mcp-hacker-news"],
            "env": common_env.copy(),
        },
    }

    return config


def get_single_server_config(server_name: str) -> dict[str, Any]:
    """
    Get configuration for a single MCP server.

    Args:
        server_name: Name of the server (e.g., 'hackernews').

    Returns:
        Configuration dictionary for the specified server.

    Raises:
        KeyError: If the server name is not found.
    """
    all_config = get_mcp_config()
    if server_name not in all_config:
        available = ", ".join(all_config.keys())
        raise KeyError(f"Unknown MCP server: {server_name}. Available: {available}")
    return all_config[server_name]


# Alternative configurations for different deployment scenarios
ALTERNATIVE_CONFIGS = {
    # SSE transport for remote MCP servers
    "hackernews_sse": {
        "transport": "sse",
        "url": os.getenv("HN_MCP_URL", "http://localhost:8001/mcp"),
    },
}
