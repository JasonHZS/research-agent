"""Configuration module for the research agent."""

from src.config.mcp_config import get_mcp_config
from src.config.settings import (
    ReaderType,
    get_app_settings,
    get_reader_config,
    resolve_reader_type,
    resolve_runtime_settings,
)

__all__ = [
    "get_mcp_config",
    "get_reader_config",
    "resolve_reader_type",
    "ReaderType",
    "get_app_settings",
    "resolve_runtime_settings",
]
