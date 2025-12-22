"""Configuration module for the research agent."""

from src.config.mcp_config import get_mcp_config
from src.config.reader_config import (
    ReaderType,
    get_reader_config,
    get_reader_type,
)

__all__ = [
    "get_mcp_config",
    "get_reader_config",
    "get_reader_type",
    "ReaderType",
]

