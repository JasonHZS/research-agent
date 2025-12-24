"""
Deep Research Mode Configuration

This module provides configuration settings for the Deep Research mode,
including iteration limits and other parameters.
"""

import os
from typing import Optional


# Default maximum iterations for the research loop
DEFAULT_MAX_ITERATIONS = 5

# Environment variable name for max iterations
ENV_MAX_ITERATIONS = "DEEP_RESEARCH_MAX_ITERATIONS"


def get_max_iterations(override: Optional[int] = None) -> int:
    """
    Get the maximum number of iterations for the deep research loop.

    Resolution order:
    1. Override parameter (from CLI)
    2. Environment variable DEEP_RESEARCH_MAX_ITERATIONS
    3. Default value (5)

    Args:
        override: Optional override value from CLI argument.

    Returns:
        Maximum number of iterations (clamped to 1-10 range).
    """
    if override is not None:
        return max(1, min(10, override))

    env_value = os.getenv(ENV_MAX_ITERATIONS)
    if env_value:
        try:
            return max(1, min(10, int(env_value)))
        except ValueError:
            pass

    return DEFAULT_MAX_ITERATIONS


def get_deep_research_settings(
    max_iterations_override: Optional[int] = None,
) -> dict:
    """
    Get all deep research configuration settings.

    Args:
        max_iterations_override: Optional override for max iterations.

    Returns:
        Dictionary containing all deep research settings.
    """
    return {
        "max_iterations": get_max_iterations(max_iterations_override),
    }

