"""Application settings and runtime config resolution.

This module centralizes environment-backed defaults and resolution rules used by
both CLI and API layers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Optional

# LLM env names and defaults
ENV_MODEL_PROVIDER = "MODEL_PROVIDER"
ENV_MODEL_NAME = "MODEL_NAME"
ENV_ENABLE_THINKING = "ENABLE_THINKING"

ALLOWED_PROVIDERS = {"aliyun", "anthropic", "openai", "openrouter"}
DEFAULT_MODEL_PROVIDER = "aliyun"
DEFAULT_MODEL_NAME_BY_PROVIDER = {
    "aliyun": "qwen3.5-plus",
    "anthropic": "claude-sonnet-4-20250514",
    "openai": "gpt-4o",
    "openrouter": "anthropic/claude-sonnet-4.5",
}

# Deep research env names and defaults
ENV_DEEP_RESEARCH_MAX_ITERATIONS = "DEEP_RESEARCH_MAX_ITERATIONS"
ENV_DEEP_RESEARCH_MAX_CONCURRENT = "DEEP_RESEARCH_MAX_CONCURRENT"
ENV_DEEP_RESEARCH_MAX_TOOL_CALLS = "DEEP_RESEARCH_MAX_TOOL_CALLS"
ENV_DEEP_RESEARCH_ALLOW_CLARIFICATION = "DEEP_RESEARCH_ALLOW_CLARIFICATION"

DEFAULT_DEEP_RESEARCH_MAX_ITERATIONS = 2
DEFAULT_DEEP_RESEARCH_MAX_CONCURRENT = 5
DEFAULT_DEEP_RESEARCH_MAX_TOOL_CALLS = 10
DEFAULT_DEEP_RESEARCH_ALLOW_CLARIFICATION = True

# API env names and defaults
ENV_API_HOST = "API_HOST"
ENV_API_PORT = "API_PORT"
DEFAULT_API_HOST = "0.0.0.0"
DEFAULT_API_PORT = 8111

# Feed digest security env names and defaults
ENV_FEEDS_ADMIN_TOKEN = "FEEDS_ADMIN_TOKEN"
ENV_FEEDS_FORCE_REFRESH_RATE_LIMIT = "FEEDS_FORCE_REFRESH_RATE_LIMIT"
ENV_FEEDS_FORCE_REFRESH_WINDOW_SECONDS = "FEEDS_FORCE_REFRESH_WINDOW_SECONDS"
DEFAULT_FEEDS_FORCE_REFRESH_RATE_LIMIT = 5
DEFAULT_FEEDS_FORCE_REFRESH_WINDOW_SECONDS = 60

# Content reader env names and defaults
ENV_CONTENT_READER_TYPE = "CONTENT_READER_TYPE"


class ReaderType(str, Enum):
    """Available content reader tool types."""

    JINA = "jina"
    ZYTE = "zyte"


DEFAULT_READER_TYPE: ReaderType = ReaderType.ZYTE


def _parse_bool(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on", "y"}


def _clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


@dataclass(frozen=True)
class LLMSettings:
    provider: str
    model_name: Optional[str]
    enable_thinking: bool


@dataclass(frozen=True)
class DeepResearchSettings:
    max_iterations: int
    max_concurrent: int
    max_tool_calls: int
    allow_clarification: bool


@dataclass(frozen=True)
class APISettings:
    host: str
    port: int


@dataclass(frozen=True)
class FeedDigestSecuritySettings:
    admin_token: Optional[str]
    force_refresh_rate_limit: int
    force_refresh_window_seconds: int


@dataclass(frozen=True)
class RuntimeSettings:
    llm: LLMSettings
    deep_research: DeepResearchSettings
    reader_type: ReaderType


@dataclass(frozen=True)
class AppSettings:
    llm: LLMSettings
    deep_research: DeepResearchSettings
    reader_type: ReaderType
    api: APISettings
    feed_digest_security: FeedDigestSecuritySettings


def resolve_llm_settings(
    provider_override: Optional[str] = None,
    model_name_override: Optional[str] = None,
    enable_thinking_override: Optional[bool] = None,
    env: Mapping[str, str] = os.environ,
) -> LLMSettings:
    provider = (provider_override or env.get(ENV_MODEL_PROVIDER) or DEFAULT_MODEL_PROVIDER).lower()
    if provider not in ALLOWED_PROVIDERS:
        valid = ", ".join(sorted(ALLOWED_PROVIDERS))
        raise ValueError(f"Invalid model provider '{provider}'. Valid options: {valid}")

    model_name = model_name_override or env.get(ENV_MODEL_NAME)

    if enable_thinking_override is not None:
        enable_thinking = enable_thinking_override
    else:
        raw_enable_thinking = env.get(ENV_ENABLE_THINKING)
        enable_thinking = _parse_bool(raw_enable_thinking) if raw_enable_thinking else False

    return LLMSettings(
        provider=provider,
        model_name=model_name,
        enable_thinking=enable_thinking,
    )


def resolve_deep_research_settings(
    max_iterations_override: Optional[int] = None,
    max_concurrent_override: Optional[int] = None,
    max_tool_calls_override: Optional[int] = None,
    allow_clarification_override: Optional[bool] = None,
    env: Mapping[str, str] = os.environ,
) -> DeepResearchSettings:
    if max_iterations_override is not None:
        max_iterations = _clamp(max_iterations_override, 1, 5)
    else:
        try:
            max_iterations = _clamp(
                int(env.get(ENV_DEEP_RESEARCH_MAX_ITERATIONS, DEFAULT_DEEP_RESEARCH_MAX_ITERATIONS)),
                1,
                5,
            )
        except ValueError:
            max_iterations = DEFAULT_DEEP_RESEARCH_MAX_ITERATIONS

    if max_concurrent_override is not None:
        max_concurrent = _clamp(max_concurrent_override, 1, 10)
    else:
        try:
            max_concurrent = _clamp(
                int(env.get(ENV_DEEP_RESEARCH_MAX_CONCURRENT, DEFAULT_DEEP_RESEARCH_MAX_CONCURRENT)),
                1,
                10,
            )
        except ValueError:
            max_concurrent = DEFAULT_DEEP_RESEARCH_MAX_CONCURRENT

    if max_tool_calls_override is not None:
        max_tool_calls = _clamp(max_tool_calls_override, 1, 20)
    else:
        try:
            max_tool_calls = _clamp(
                int(env.get(ENV_DEEP_RESEARCH_MAX_TOOL_CALLS, DEFAULT_DEEP_RESEARCH_MAX_TOOL_CALLS)),
                1,
                20,
            )
        except ValueError:
            max_tool_calls = DEFAULT_DEEP_RESEARCH_MAX_TOOL_CALLS

    if allow_clarification_override is not None:
        allow_clarification = allow_clarification_override
    else:
        raw_allow_clarification = env.get(ENV_DEEP_RESEARCH_ALLOW_CLARIFICATION)
        if raw_allow_clarification:
            allow_clarification = _parse_bool(raw_allow_clarification)
        else:
            allow_clarification = DEFAULT_DEEP_RESEARCH_ALLOW_CLARIFICATION

    return DeepResearchSettings(
        max_iterations=max_iterations,
        max_concurrent=max_concurrent,
        max_tool_calls=max_tool_calls,
        allow_clarification=allow_clarification,
    )


def resolve_api_settings(env: Mapping[str, str] = os.environ) -> APISettings:
    host = env.get(ENV_API_HOST, DEFAULT_API_HOST)
    try:
        port = int(env.get(ENV_API_PORT, str(DEFAULT_API_PORT)))
    except ValueError:
        port = DEFAULT_API_PORT

    return APISettings(host=host, port=port)


def resolve_feed_digest_security_settings(
    env: Mapping[str, str] = os.environ,
) -> FeedDigestSecuritySettings:
    admin_token = env.get(ENV_FEEDS_ADMIN_TOKEN)
    if admin_token is not None:
        admin_token = admin_token.strip() or None

    try:
        rate_limit = int(
            env.get(
                ENV_FEEDS_FORCE_REFRESH_RATE_LIMIT,
                str(DEFAULT_FEEDS_FORCE_REFRESH_RATE_LIMIT),
            )
        )
    except ValueError:
        rate_limit = DEFAULT_FEEDS_FORCE_REFRESH_RATE_LIMIT

    try:
        window_seconds = int(
            env.get(
                ENV_FEEDS_FORCE_REFRESH_WINDOW_SECONDS,
                str(DEFAULT_FEEDS_FORCE_REFRESH_WINDOW_SECONDS),
            )
        )
    except ValueError:
        window_seconds = DEFAULT_FEEDS_FORCE_REFRESH_WINDOW_SECONDS

    return FeedDigestSecuritySettings(
        admin_token=admin_token,
        force_refresh_rate_limit=_clamp(rate_limit, 1, 200),
        force_refresh_window_seconds=_clamp(window_seconds, 1, 3600),
    )


def resolve_reader_type(env: Mapping[str, str] = os.environ) -> ReaderType:
    if value := env.get(ENV_CONTENT_READER_TYPE):
        try:
            return ReaderType(value.lower())
        except ValueError:
            valid_values = ", ".join(rt.value for rt in ReaderType)
            raise ValueError(
                f"Invalid CONTENT_READER_TYPE '{value}'. "
                f"Valid options: {valid_values}"
            )

    return DEFAULT_READER_TYPE


def get_reader_config(env: Mapping[str, str] = os.environ) -> dict:
    reader_type = resolve_reader_type(env=env)
    config = {
        "type": reader_type,
        "name": reader_type.value,
    }

    if reader_type == ReaderType.JINA:
        config["api_key_env"] = "JINA_API_KEY"
        config["description"] = "Jina Reader - converts web pages to markdown"
    elif reader_type == ReaderType.ZYTE:
        config["api_key_env"] = "ZYTE_API_KEY"
        config["description"] = "Zyte API - extracts structured article content"

    return config


def resolve_runtime_settings(
    *,
    provider_override: Optional[str] = None,
    model_name_override: Optional[str] = None,
    enable_thinking_override: Optional[bool] = None,
    max_iterations_override: Optional[int] = None,
    max_concurrent_override: Optional[int] = None,
    max_tool_calls_override: Optional[int] = None,
    allow_clarification_override: Optional[bool] = None,
    env: Mapping[str, str] = os.environ,
) -> RuntimeSettings:
    return RuntimeSettings(
        llm=resolve_llm_settings(
            provider_override=provider_override,
            model_name_override=model_name_override,
            enable_thinking_override=enable_thinking_override,
            env=env,
        ),
        deep_research=resolve_deep_research_settings(
            max_iterations_override=max_iterations_override,
            max_concurrent_override=max_concurrent_override,
            max_tool_calls_override=max_tool_calls_override,
            allow_clarification_override=allow_clarification_override,
            env=env,
        ),
        reader_type=resolve_reader_type(env=env),
    )


def get_app_settings(env: Mapping[str, str] = os.environ) -> AppSettings:
    return AppSettings(
        llm=resolve_llm_settings(env=env),
        deep_research=resolve_deep_research_settings(env=env),
        reader_type=resolve_reader_type(env=env),
        api=resolve_api_settings(env=env),
        feed_digest_security=resolve_feed_digest_security_settings(env=env),
    )


def get_default_model_for_provider(provider: str) -> str:
    return DEFAULT_MODEL_NAME_BY_PROVIDER.get(provider, DEFAULT_MODEL_NAME_BY_PROVIDER[DEFAULT_MODEL_PROVIDER])
