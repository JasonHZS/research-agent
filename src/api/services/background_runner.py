"""Background agent run lifecycle and subscriber fan-out."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncGenerator, Callable
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import uuid4

from src.api.schemas.chat import StreamEvent, StreamEventType
from src.api.services.snapshot import (
    StreamingSnapshot,
    apply_event_to_snapshot,
    build_snapshot_from_state,
)


@dataclass
class BackgroundRun:
    conversation_id: str
    request_id: str
    is_deep_research: bool
    task: Optional[asyncio.Task]
    snapshot: StreamingSnapshot
    subscribers: set[asyncio.Queue] = field(default_factory=set)
    terminal_event: Optional[StreamEvent] = None
    completed_at: Optional[float] = None


class BackgroundRunner:
    """Schedules agent streams and lets clients subscribe or resume them."""

    def __init__(
        self,
        *,
        stream_events: Callable[..., AsyncGenerator[StreamEvent, None]],
        get_agent: Callable[[str], Any],
        logger: Any,
        completed_run_ttl_seconds: float,
    ) -> None:
        self._stream_events = stream_events
        self._get_agent = get_agent
        self._logger = logger
        self._completed_run_ttl_seconds = completed_run_ttl_seconds
        self.background_runs: dict[str, BackgroundRun] = {}

    def cancel_run(self, conversation_id: str) -> None:
        run = self.background_runs.pop(conversation_id, None)
        if run is not None and run.task is not None:
            run.task.cancel()

    async def _broadcast_to_subscribers(
        self,
        run: BackgroundRun,
        event: Optional[StreamEvent],
    ) -> None:
        stale_subscribers: list[asyncio.Queue] = []
        for subscriber in run.subscribers:
            try:
                subscriber.put_nowait(event)
            except asyncio.QueueFull:
                stale_subscribers.append(subscriber)

        for stale_subscriber in stale_subscribers:
            run.subscribers.discard(stale_subscriber)

    async def _run_in_background(
        self,
        run: BackgroundRun,
        message: str,
        model_provider: Optional[str],
        model_name: Optional[str],
    ) -> None:
        try:
            async for event in self._stream_events(
                conversation_id=run.conversation_id,
                message=message,
                model_provider=model_provider,
                model_name=model_name,
                is_deep_research=run.is_deep_research,
            ):
                apply_event_to_snapshot(run.snapshot, event)
                if event.type in {StreamEventType.MESSAGE_COMPLETE, StreamEventType.ERROR}:
                    run.terminal_event = event
                await self._broadcast_to_subscribers(run, event)
        except asyncio.CancelledError:
            run.snapshot.error = "Run was cancelled"
            raise
        except Exception as run_error:
            self._logger.exception(
                "Background run failed unexpectedly",
                conversation_id=run.conversation_id,
                error=str(run_error),
            )
            error_event = StreamEvent(
                type=StreamEventType.ERROR,
                data={"message": str(run_error)},
            )
            apply_event_to_snapshot(run.snapshot, error_event)
            run.terminal_event = error_event
            await self._broadcast_to_subscribers(run, error_event)
        finally:
            run.snapshot.is_running = False
            run.completed_at = time.monotonic()
            await self._broadcast_to_subscribers(run, None)

    def purge_stale_runs(self) -> None:
        """Remove completed BackgroundRun objects older than TTL."""
        now = time.monotonic()
        stale_ids = [
            conversation_id
            for conversation_id, run in self.background_runs.items()
            if run.completed_at is not None
            and (now - run.completed_at) > self._completed_run_ttl_seconds
        ]
        for conversation_id in stale_ids:
            self.background_runs.pop(conversation_id, None)

    def get_background_run(self, conversation_id: str) -> Optional[BackgroundRun]:
        """Return the current run after enforcing TTL for completed entries."""
        self.purge_stale_runs()
        return self.background_runs.get(conversation_id)

    def start_background_run(
        self,
        conversation_id: str,
        message: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
        request_id: Optional[str] = None,
    ) -> BackgroundRun:
        existing_run = self.get_background_run(conversation_id)
        if (
            existing_run is not None
            and existing_run.task is not None
            and not existing_run.task.done()
        ):
            raise ValueError(f"Conversation {conversation_id} already has an active run")

        resolved_request_id = request_id or uuid4().hex
        run = BackgroundRun(
            conversation_id=conversation_id,
            request_id=resolved_request_id,
            is_deep_research=is_deep_research,
            task=None,
            snapshot=StreamingSnapshot(request_id=resolved_request_id),
        )
        run.task = asyncio.create_task(
            self._run_in_background(
                run=run,
                message=message,
                model_provider=model_provider,
                model_name=model_name,
            )
        )
        self.background_runs[conversation_id] = run
        return run

    async def subscribe_to_run(
        self,
        conversation_id: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        run = self.get_background_run(conversation_id)
        if run is None:
            raise ValueError(f"No background run found for conversation {conversation_id}")

        queue: asyncio.Queue = asyncio.Queue()
        if run.snapshot.is_running:
            run.subscribers.add(queue)

        try:
            yield StreamEvent(
                type=StreamEventType.SNAPSHOT,
                data=build_snapshot_from_state(
                    agent=self._get_agent(conversation_id),
                    conversation_id=conversation_id,
                    run_snapshot=run.snapshot,
                    logger=self._logger,
                ),
            )

            if not run.snapshot.is_running:
                if run.terminal_event is not None:
                    yield run.terminal_event
                return

            while True:
                event = await queue.get()
                if event is None:
                    break
                yield event
        finally:
            run.subscribers.discard(queue)

    def has_background_run(self, conversation_id: str) -> bool:
        return self.get_background_run(conversation_id) is not None
