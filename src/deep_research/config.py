"""Deep research runtime config parsing.

Provides a single parser for RunnableConfig configurable fields and keeps
backward compatibility with legacy key names.
"""

from __future__ import annotations

from typing import Any

from langchain_core.runnables import RunnableConfig

from src.config.settings import get_app_settings

from .state import DeepResearchConfig


def _get_configurable(config: RunnableConfig | None) -> dict[str, Any]:
    if not config:
        return {}
    configurable = config.get("configurable", {})
    return configurable if isinstance(configurable, dict) else {}


def _get_value(configurable: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in configurable and configurable[key] is not None:
            return configurable[key]
    return default


def parse_deep_research_config(config: RunnableConfig | None) -> DeepResearchConfig:
    app_settings = get_app_settings()
    configurable = _get_configurable(config)

    return DeepResearchConfig(
        max_tool_calls=_get_value(
            configurable,
            "max_tool_calls",
            "max_tool_calls_per_researcher",
            default=app_settings.deep_research.max_tool_calls,
        ),
        max_iterations=_get_value(
            configurable,
            "max_iterations",
            "max_review_iterations",
            default=app_settings.deep_research.max_iterations,
        ),
        model_provider=_get_value(
            configurable,
            "model_provider",
            default=app_settings.llm.provider,
        ),
        model_name=_get_value(
            configurable,
            "model_name",
            default=app_settings.llm.model_name,
        ),
        enable_thinking=_get_value(
            configurable,
            "enable_thinking",
            default=app_settings.llm.enable_thinking,
        ),
        allow_clarification=_get_value(
            configurable,
            "allow_clarification",
            default=app_settings.deep_research.allow_clarification,
        ),
        verbose=_get_value(configurable, "verbose", default=False),
    )
