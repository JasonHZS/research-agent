"""Regression tests for deep research runtime config and researcher compression."""

import asyncio
from types import SimpleNamespace

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
