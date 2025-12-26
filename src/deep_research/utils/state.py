"""
State helpers.

Utility to read state fields regardless of whether LangGraph passes a plain dict
or an object with attributes.
"""

from typing import Any


def get_state_value(state: Any, key: str, default: Any = None) -> Any:
    """Retrieve a state field supporting both dict and attribute access."""
    if isinstance(state, dict):
        return state.get(key, default)
    return getattr(state, key, default)

