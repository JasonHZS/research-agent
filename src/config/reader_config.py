"""
Content Reader Configuration

This module provides configuration for the Content Reader agent,
allowing selection between different web content reading tools.

Selection can be controlled at runtime via the CONTENT_READER_TYPE
environment variable:
- "jina" (default): free Jina Reader
- "zyte": Zyte API (paid)
"""

import os
from enum import Enum


class ReaderType(str, Enum):
    """Available content reader tool types."""

    JINA = "jina"  # Jina Reader - free, returns markdown
    ZYTE = "zyte"  # Zyte API - paid, returns structured article data


# Default reader if none specified via environment
DEFAULT_READER_TYPE: ReaderType = ReaderType.JINA


def get_reader_type() -> ReaderType:
    """
    Get the configured content reader type.

    Returns:
        The configured ReaderType enum value.

    Raises:
        ValueError: If CONTENT_READER_TYPE is set to an invalid value.
    """
    if value := os.getenv("CONTENT_READER_TYPE"):
        try:
            return ReaderType(value.lower())
        except ValueError:
            valid_values = ", ".join(rt.value for rt in ReaderType)
            raise ValueError(
                f"Invalid CONTENT_READER_TYPE '{value}'. "
                f"Valid options: {valid_values}"
            )

    return DEFAULT_READER_TYPE


def get_reader_config() -> dict:
    """
    Get the full reader configuration.

    Returns:
        Dictionary containing reader configuration details.
    """
    reader_type = get_reader_type()

    config = {
        "type": reader_type,
        "name": reader_type.value,
    }

    # Add type-specific configuration
    if reader_type == ReaderType.JINA:
        config["api_key_env"] = "JINA_API_KEY"
        config["description"] = "Jina Reader - converts web pages to markdown"
    elif reader_type == ReaderType.ZYTE:
        config["api_key_env"] = "ZYTE_API_KEY"
        config["description"] = "Zyte API - extracts structured article content"

    return config
