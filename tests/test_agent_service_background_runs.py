import asyncio
import time
from types import SimpleNamespace

import pytest

from src.api.schemas.chat import StreamEvent, StreamEventType
from src.api.services.agent_service import AgentService


class _FakeAgent:
    def __init__(self, values):
        self._values = values

    def get_state(self, _config):
        return SimpleNamespace(values=self._values)


class _BrokenAgent:
    """Agent whose get_state always raises."""

    def get_state(self, _config):
        raise RuntimeError("checkpoint corrupted")


@pytest.mark.asyncio
async def test_background_run_completes_without_active_subscriber(monkeypatch: pytest.MonkeyPatch):
    service = AgentService()

    async def fake_stream_agent_events(**_kwargs):
        await asyncio.sleep(0.01)
        yield StreamEvent(type=StreamEventType.TOKEN, data={"content": "hello"})
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            data={"is_clarification": False},
        )

    monkeypatch.setattr(service, "_stream_agent_events", fake_stream_agent_events)

    run = service.start_background_run(
        conversation_id="background-no-subscriber",
        message="test",
        request_id="req-background",
    )
    await run.task

    assert run.snapshot.content == "hello"
    assert run.snapshot.is_running is False
    assert run.terminal_event is not None
    assert run.terminal_event.type == StreamEventType.MESSAGE_COMPLETE


@pytest.mark.asyncio
async def test_resume_subscription_receives_snapshot_from_graph_state(monkeypatch: pytest.MonkeyPatch):
    service = AgentService()

    async def fake_stream_agent_events(**_kwargs):
        yield StreamEvent(type=StreamEventType.PROGRESS, data={"node": "working"})
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            data={"is_clarification": False},
        )

    monkeypatch.setattr(service, "_stream_agent_events", fake_stream_agent_events)
    service._agents["resume-session"] = _FakeAgent({"final_report": "Recovered report"})

    run = service.start_background_run(
        conversation_id="resume-session",
        message="test",
        request_id="req-resume",
    )
    await run.task

    events = []
    async for event in service.subscribe_to_run("resume-session"):
        events.append(event)

    assert events[0].type == StreamEventType.SNAPSHOT
    assert events[0].data["content"] == "Recovered report"
    assert events[0].data["is_running"] is False
    assert events[1].type == StreamEventType.MESSAGE_COMPLETE


@pytest.mark.asyncio
async def test_duplicate_active_run_raises(monkeypatch: pytest.MonkeyPatch):
    """Starting a second run on the same conversation while one is active should raise."""
    service = AgentService()

    # A stream that never completes on its own
    async def slow_stream(**_kwargs):
        await asyncio.sleep(10)
        yield StreamEvent(type=StreamEventType.MESSAGE_COMPLETE, data={})

    monkeypatch.setattr(service, "_stream_agent_events", slow_stream)

    run = service.start_background_run(
        conversation_id="dup-test",
        message="first",
        request_id="req-1",
    )

    with pytest.raises(ValueError, match="already has an active run"):
        service.start_background_run(
            conversation_id="dup-test",
            message="second",
            request_id="req-2",
        )

    # Cleanup
    run.task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await run.task


@pytest.mark.asyncio
async def test_cancellation_records_error_in_snapshot(monkeypatch: pytest.MonkeyPatch):
    """Cancelling a background run should set an error message in the snapshot."""
    service = AgentService()

    async def slow_stream(**_kwargs):
        await asyncio.sleep(10)
        yield StreamEvent(type=StreamEventType.MESSAGE_COMPLETE, data={})

    monkeypatch.setattr(service, "_stream_agent_events", slow_stream)

    run = service.start_background_run(
        conversation_id="cancel-test",
        message="test",
        request_id="req-cancel",
    )

    # Let the task start
    await asyncio.sleep(0.01)
    run.task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await run.task

    assert run.snapshot.is_running is False
    assert run.snapshot.error == "Run was cancelled"
    assert run.completed_at is not None


@pytest.mark.asyncio
async def test_stream_error_propagates_to_snapshot(monkeypatch: pytest.MonkeyPatch):
    """An exception in the stream should be captured as an error in the snapshot."""
    service = AgentService()

    async def failing_stream(**_kwargs):
        yield StreamEvent(type=StreamEventType.TOKEN, data={"content": "partial"})
        raise RuntimeError("upstream exploded")

    monkeypatch.setattr(service, "_stream_agent_events", failing_stream)

    run = service.start_background_run(
        conversation_id="error-test",
        message="test",
        request_id="req-error",
    )
    await run.task

    assert run.snapshot.is_running is False
    assert run.snapshot.content == "partial"
    assert run.snapshot.error == "upstream exploded"
    assert run.terminal_event is not None
    assert run.terminal_event.type == StreamEventType.ERROR


@pytest.mark.asyncio
async def test_multiple_concurrent_subscribers(monkeypatch: pytest.MonkeyPatch):
    """Multiple subscribers should all receive the same live events."""
    service = AgentService()
    barrier = asyncio.Event()

    async def gated_stream(**_kwargs):
        await barrier.wait()
        yield StreamEvent(type=StreamEventType.TOKEN, data={"content": "shared"})
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            data={"is_clarification": False},
        )

    monkeypatch.setattr(service, "_stream_agent_events", gated_stream)

    service.start_background_run(
        conversation_id="multi-sub",
        message="test",
        request_id="req-multi",
    )

    # Collect events from two concurrent subscribers
    async def collect_events() -> list[StreamEvent]:
        events = []
        async for event in service.subscribe_to_run("multi-sub"):
            events.append(event)
        return events

    sub1_task = asyncio.create_task(collect_events())
    sub2_task = asyncio.create_task(collect_events())

    # Give subscribers time to register
    await asyncio.sleep(0.05)

    # Unblock the stream
    barrier.set()

    events1 = await sub1_task
    events2 = await sub2_task

    # Both should have snapshot + token + message_complete
    assert len(events1) == 3
    assert len(events2) == 3

    # Both got the same token
    assert events1[1].type == StreamEventType.TOKEN
    assert events2[1].type == StreamEventType.TOKEN
    assert events1[1].data["content"] == "shared"
    assert events2[1].data["content"] == "shared"


@pytest.mark.asyncio
async def test_degraded_snapshot_when_get_state_fails(monkeypatch: pytest.MonkeyPatch):
    """When agent.get_state() raises, snapshot should be marked as degraded."""
    service = AgentService()

    async def fake_stream(**_kwargs):
        yield StreamEvent(type=StreamEventType.TOKEN, data={"content": "ok"})
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            data={"is_clarification": False},
        )

    monkeypatch.setattr(service, "_stream_agent_events", fake_stream)
    service._agents["degraded-session"] = _BrokenAgent()

    run = service.start_background_run(
        conversation_id="degraded-session",
        message="test",
        request_id="req-degraded",
    )
    await run.task

    events = []
    async for event in service.subscribe_to_run("degraded-session"):
        events.append(event)

    snapshot_data = events[0].data
    assert snapshot_data["state_degraded"] is True
    assert snapshot_data["content"] == "ok"


@pytest.mark.asyncio
async def test_completed_run_ttl_is_enforced_on_resume_lookup(monkeypatch: pytest.MonkeyPatch):
    service = AgentService()

    async def fake_stream_agent_events(**_kwargs):
        yield StreamEvent(type=StreamEventType.TOKEN, data={"content": "done"})
        yield StreamEvent(
            type=StreamEventType.MESSAGE_COMPLETE,
            data={"is_clarification": False},
        )

    monkeypatch.setattr(service, "_stream_agent_events", fake_stream_agent_events)

    run = service.start_background_run(
        conversation_id="expired-run",
        message="test",
        request_id="req-expired",
    )
    await run.task
    run.completed_at = time.monotonic() - service.COMPLETED_RUN_TTL_SECONDS - 1

    assert service.has_background_run("expired-run") is False
    assert "expired-run" not in service._background_runs

    with pytest.raises(ValueError, match="No background run found"):
        async for _event in service.subscribe_to_run("expired-run"):
            pass
