"""
LLM Configuration Resolution

Resolves model provider, model name, and thinking mode from:
1) Caller-provided overrides (CLI, UI/backend, etc.)
2) Environment variables (MODEL_PROVIDER, MODEL_NAME, ENABLE_THINKING)
3) Code defaults (fallback)

The goal is to keep configuration resolution cohesive and decoupled from any
particular interface (CLI/frontend), so future UI layers can reuse it.
"""

import os
from typing import Mapping, Optional

# Supported providers and defaults
ALLOWED_PROVIDERS = {"aliyun", "anthropic", "openai"}
DEFAULT_PROVIDER = "aliyun"


def _parse_bool(value: str) -> bool:
    """Parse common truthy strings into boolean."""
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def resolve_model_provider(
    override: Optional[str],
    env: Mapping[str, str] = os.environ,
) -> str:
    """
    Resolve the model provider from an override or environment.

    Args:
        override: Provider passed in by caller (CLI/UI/backend).
        env: Environment mapping (injectable for tests).

    Returns:
        Validated provider string.

    Raises:
        ValueError: If the provider is not in ALLOWED_PROVIDERS.
    """
    provider = (override or env.get("MODEL_PROVIDER") or DEFAULT_PROVIDER).lower()

    if provider not in ALLOWED_PROVIDERS:
        valid = ", ".join(sorted(ALLOWED_PROVIDERS))
        raise ValueError(f"Invalid model provider '{provider}'. Valid options: {valid}")

    return provider


def resolve_model_name(
    override: Optional[str],
    env: Mapping[str, str] = os.environ,
) -> Optional[str]:
    """
    Resolve the model name from an override or environment.

    Args:
        override: Model name passed in by caller (CLI/UI/backend).
        env: Environment mapping (injectable for tests).

    Returns:
        Model name string or None to use provider defaults.
    """
    return override or env.get("MODEL_NAME")


def resolve_enable_thinking(
    override: Optional[bool],
    env: Mapping[str, str] = os.environ,
) -> bool:
    """
    Resolve thinking mode toggle from an override or environment.

    override=True has highest priority; when override is False/None,
    env ENABLE_THINKING is considered; otherwise defaults to False.
    """
    if override is True:
        return True

    env_val = env.get("ENABLE_THINKING")
    if env_val is not None:
        return _parse_bool(env_val)

    return False


def get_model_settings(
    provider_override: Optional[str] = None,
    model_name_override: Optional[str] = None,
    enable_thinking_override: Optional[bool] = None,
    env: Mapping[str, str] = os.environ,
) -> dict:
    """
    Resolve all model-related settings with precedence:
    caller overrides > env > defaults.

    Args:
        provider_override: Provider from caller (CLI/UI/backend).
        model_name_override: Model name from caller.
        enable_thinking_override: Thinking mode from caller.
        env: Environment mapping (injectable for tests/other runtimes).

    Returns:
        Dict with keys: provider, model_name, enable_thinking
    """
    provider = resolve_model_provider(provider_override, env)
    model_name = resolve_model_name(model_name_override, env)
    enable_thinking = resolve_enable_thinking(enable_thinking_override, env)

    return {
        "provider": provider,
        "model_name": model_name,
        "enable_thinking": enable_thinking,
    }
