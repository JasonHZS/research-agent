"""Regression tests for deep research runtime config and researcher compression."""

import asyncio
from types import SimpleNamespace

from src.config.llm_factory import create_llm, resolve_provider_for_model
from src.config.settings import get_default_model_for_provider, resolve_llm_settings
from src.deep_research.config import parse_deep_research_config
from src.deep_research.nodes import researcher as researcher_node
from src.deep_research.state import Section
from src.deep_research.structured_outputs import SectionContent


def _build_settings_stub():
    return SimpleNamespace(
        llm=SimpleNamespace(
            provider="stub-provider",
            model_name="stub-model",
            enable_thinking=False,
        ),
        deep_research=SimpleNamespace(
            max_tool_calls=10,
            max_iterations=2,
            allow_clarification=True,
        ),
    )


def test_parse_deep_research_config_accepts_legacy_keys(monkeypatch):
    monkeypatch.setattr("src.deep_research.config.get_app_settings", _build_settings_stub)

    parsed = parse_deep_research_config(
        {
            "configurable": {
                "max_tool_calls_per_researcher": 7,
                "max_review_iterations": 4,
            }
        }
    )

    assert parsed.max_tool_calls == 7
    assert parsed.max_iterations == 4


def test_parse_deep_research_config_prefers_new_keys(monkeypatch):
    monkeypatch.setattr("src.deep_research.config.get_app_settings", _build_settings_stub)

    parsed = parse_deep_research_config(
        {
            "configurable": {
                "max_tool_calls": 5,
                "max_tool_calls_per_researcher": 7,
                "max_iterations": 3,
                "max_review_iterations": 4,
            }
        }
    )

    assert parsed.max_tool_calls == 5
    assert parsed.max_iterations == 3


def test_resolve_provider_for_openrouter_full_model_name():
    assert resolve_provider_for_model("openai/gpt-5", "aliyun") == "openrouter"


def test_resolve_llm_settings_auto_switches_for_openrouter_full_model_name():
    settings = resolve_llm_settings(
        provider_override="aliyun",
        model_name_override="openai/gpt-5",
        env={},
    )

    assert settings.provider == "openrouter"
    assert settings.model_name == "openai/gpt-5"


def test_resolve_llm_settings_keeps_deepseek_v4_on_aliyun():
    settings = resolve_llm_settings(
        provider_override="aliyun",
        model_name_override="deepseek-v4-pro",
        env={},
    )

    assert settings.provider == "aliyun"
    assert settings.model_name == "deepseek-v4-pro"


def test_create_aliyun_deepseek_v4_llm_uses_dashscope_key(monkeypatch):
    monkeypatch.setenv("ALIYUN_API_KEY", "test-key")

    llm = create_llm("aliyun", "deepseek-v4-flash")

    assert llm.model_name == "deepseek-v4-flash"
    assert llm.openai_api_base == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_create_openrouter_llm_uses_settings_default(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")

    llm = create_llm("openrouter")

    assert llm.model_name == get_default_model_for_provider("openrouter")


def test_resolve_llm_settings_rejects_deepseek_provider():
    try:
        resolve_llm_settings(provider_override="deepseek", env={})
    except ValueError as exc:
        assert "Invalid model provider 'deepseek'" in str(exc)
    else:
        raise AssertionError("deepseek provider should be rejected")


def test_compress_and_output_node_uses_runtime_config(monkeypatch):
    class _FakeStructuredLLM:
        async def ainvoke(self, _prompt_text):
            return SectionContent(title="stub", content="compressed content", sources=["s1"])

    class _FakeLLM:
        def with_structured_output(self, _schema):
            return _FakeStructuredLLM()

    seen = {}

    def _fake_parse(_config):
        return SimpleNamespace(model_provider="provider-x", model_name="model-y")

    def _fake_get_llm(provider, model_name):
        seen["provider"] = provider
        seen["model_name"] = model_name
        return _FakeLLM()

    monkeypatch.setattr(researcher_node, "parse_deep_research_config", _fake_parse)
    monkeypatch.setattr(researcher_node, "get_llm", _fake_get_llm)
    monkeypatch.setattr(researcher_node, "load_prompt", lambda *_args, **_kwargs: "prompt")

    result = asyncio.run(
        researcher_node._compress_and_output_node(
            {
                "section": Section(title="Sec", description="Desc"),
                "researcher_messages": [],
            },
            config={},
        )
    )

    assert seen == {"provider": "provider-x", "model_name": "model-y"}
    assert result["sections"][0].status == "completed"
    assert result["sections"][0].content == "compressed content"
