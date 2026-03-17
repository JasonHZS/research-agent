import asyncio
from types import SimpleNamespace

import pytest
from langchain_core.messages import AIMessage

import src.api.services.agent_service as agent_service_module
from src.api.schemas.chat import StreamEventType
from src.api.services.agent_service import AgentService


class _FakeAgent:
    def get_state(self, _config):
        return SimpleNamespace(values={})


@pytest.mark.asyncio
async def test_deep_research_emits_keepalive_during_idle_stream(monkeypatch: pytest.MonkeyPatch):
    service = AgentService()

    runtime_settings = SimpleNamespace(
        llm=SimpleNamespace(provider="aliyun", model_name="test-model"),
        deep_research=SimpleNamespace(
            max_iterations=1,
            max_tool_calls=1,
            max_concurrent=1,
        ),
    )

    async def fake_run_research_stream(**_kwargs):
        await asyncio.sleep(0.05)
        yield (
            "messages",
            (AIMessage(content="hidden stage output"), {"langgraph_node": "discover_tools"}),
        )
        yield (
            "messages",
            (AIMessage(content="final answer"), {"langgraph_node": "final_report"}),
        )

    monkeypatch.setattr(
        service,
        "_get_or_create_agent",
        lambda *args, **kwargs: _FakeAgent(),
    )
    monkeypatch.setattr(
        service,
        "DEEP_RESEARCH_HEARTBEAT_INTERVAL_SECONDS",
        0.01,
    )
    monkeypatch.setattr(
        agent_service_module,
        "resolve_runtime_settings",
        lambda **kwargs: runtime_settings,
    )
    monkeypatch.setattr(
        agent_service_module,
        "run_research_stream",
        fake_run_research_stream,
    )

    events = []
    async for event in service.stream_response(
        conversation_id="keepalive-test",
        message="test query",
        is_deep_research=True,
    ):
        events.append(event)

    progress_events = [event for event in events if event.type == StreamEventType.PROGRESS]
    token_events = [event for event in events if event.type == StreamEventType.TOKEN]

    assert progress_events
    assert progress_events[0].data["node"] == "working"
    assert any(event.data["node"] == "discover_tools" for event in progress_events)
    assert [event.data["content"] for event in token_events] == ["final answer"]


@pytest.mark.asyncio
async def test_deep_research_reports_final_report_before_tokens(
    monkeypatch: pytest.MonkeyPatch,
):
    service = AgentService()

    runtime_settings = SimpleNamespace(
        llm=SimpleNamespace(provider="aliyun", model_name="test-model"),
        deep_research=SimpleNamespace(
            max_iterations=1,
            max_tool_calls=1,
            max_concurrent=1,
        ),
    )

    async def fake_run_research_stream(**_kwargs):
        yield ("updates", {"review": {}})
        yield ("updates", {"final_report": {}})
        yield (
            "messages",
            (AIMessage(content="final answer"), {"langgraph_node": "final_report"}),
        )

    monkeypatch.setattr(
        service,
        "_get_or_create_agent",
        lambda *args, **kwargs: _FakeAgent(),
    )
    monkeypatch.setattr(
        agent_service_module,
        "resolve_runtime_settings",
        lambda **kwargs: runtime_settings,
    )
    monkeypatch.setattr(
        agent_service_module,
        "run_research_stream",
        fake_run_research_stream,
    )

    events = []
    async for event in service.stream_response(
        conversation_id="final-report-progress-test",
        message="test query",
        is_deep_research=True,
    ):
        events.append(event)

    event_types = [event.type for event in events]
    progress_nodes = [event.data["node"] for event in events if event.type == StreamEventType.PROGRESS]
    final_report_progress_index = next(
        index
        for index, event in enumerate(events)
        if event.type == StreamEventType.PROGRESS and event.data["node"] == "final_report"
    )
    first_token_index = next(
        index for index, event in enumerate(events) if event.type == StreamEventType.TOKEN
    )

    assert event_types.count(StreamEventType.PROGRESS) >= 2
    assert progress_nodes == ["review", "final_report"]
    assert final_report_progress_index < first_token_index
