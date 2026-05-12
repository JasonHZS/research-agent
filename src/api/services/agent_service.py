"""Agent service facade - Bridge between API routes and research agents."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any, Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from src.agent.research_agent import (
    create_research_agent,
    run_research_async,
    run_research_stream,
)
from src.api.schemas.chat import ModelInfo, StreamEvent
from src.api.services.background_runner import BackgroundRun, BackgroundRunner
from src.api.services.message_utils import (
    extract_messages_recursive,
    format_tool_result,
    is_error_result,
    is_stream_disconnect_error,
    sanitize_tool_args,
)
from src.api.services.snapshot import (
    apply_event_to_snapshot,
    build_snapshot_from_state,
)
from src.api.services.stream_event_processor import StreamEventProcessor
from src.config.llm_factory import ALIYUN_MODELS, OPENROUTER_MODELS
from src.config.settings import resolve_runtime_settings
from src.deep_research.graph import build_deep_research_graph
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class AgentService:
    """Service for managing research agent instances and streaming."""

    DEEP_RESEARCH_HEARTBEAT_INTERVAL_SECONDS = 15.0
    DEEP_RESEARCH_HEARTBEAT_FALLBACK_NODE = "working"
    COMPLETED_RUN_TTL_SECONDS = 30 * 60

    # Compatibility aliases for older tests and call sites that used the static
    # helpers directly from AgentService.
    _format_tool_result = staticmethod(format_tool_result)
    _is_error_result = staticmethod(is_error_result)
    _is_stream_disconnect_error = staticmethod(is_stream_disconnect_error)
    _sanitize_tool_args = staticmethod(sanitize_tool_args)
    _extract_messages_recursive = staticmethod(extract_messages_recursive)
    _apply_event_to_snapshot = staticmethod(apply_event_to_snapshot)

    def __init__(self):
        """Initialize the agent service."""
        self._agents: dict[str, Any] = {}
        self._checkpointers: dict[tuple[str, bool], MemorySaver] = {}
        self._stores: dict[tuple[str, bool], InMemoryStore] = {}
        self._agent_configs: dict[str, tuple[str, Optional[str], bool]] = {}
        self._background_runner = BackgroundRunner(
            stream_events=lambda **kwargs: self._stream_agent_events(**kwargs),
            get_agent=lambda conversation_id: self._agents.get(conversation_id),
            logger=logger,
            completed_run_ttl_seconds=self.COMPLETED_RUN_TTL_SECONDS,
        )

    @property
    def _background_runs(self) -> dict[str, BackgroundRun]:
        """Compatibility view of managed background runs."""
        return self._background_runner.background_runs

    def _get_or_create_agent(
        self,
        conversation_id: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> Any:
        """Get existing agent or create a new one for the conversation."""
        runtime_settings = resolve_runtime_settings(
            provider_override=model_provider,
            model_name_override=model_name,
        )
        requested_provider = runtime_settings.llm.provider
        requested_model = runtime_settings.llm.model_name

        state_key = (conversation_id, is_deep_research)
        checkpointer = self._checkpointers.get(state_key)
        store = self._stores.get(state_key)

        if checkpointer is None:
            checkpointer = MemorySaver()
            self._checkpointers[state_key] = checkpointer
        if store is None:
            store = InMemoryStore()
            self._stores[state_key] = store

        cached_agent = self._agents.get(conversation_id)
        cached_config = self._agent_configs.get(conversation_id)

        requested_config = (requested_provider, requested_model, is_deep_research)
        if cached_agent and cached_config == requested_config:
            logger.debug(
                "Reusing existing agent",
                conversation_id=conversation_id,
            )
            return cached_agent

        if cached_agent:
            logger.info(
                "Recreating agent due to config change",
                conversation_id=conversation_id,
                old_config=str(cached_config),
                new_config=str(requested_config),
            )

        try:
            if is_deep_research:
                logger.info(
                    "Creating Deep Research agent",
                    conversation_id=conversation_id,
                    provider=requested_provider,
                    model=requested_model,
                )
                agent = build_deep_research_graph(
                    model_provider=requested_provider,
                    model_name=requested_model,
                    checkpointer=checkpointer,
                    store=store,
                )
            else:
                logger.info(
                    "Creating Research agent",
                    conversation_id=conversation_id,
                    provider=requested_provider,
                    model=requested_model,
                )
                agent = create_research_agent(
                    model_provider=requested_provider,
                    model_name=requested_model,
                    checkpointer=checkpointer,
                    store=store,
                    debug=False,
                )

            logger.info(
                "Agent ready",
                conversation_id=conversation_id,
                provider=requested_provider,
                model=requested_model,
                is_deep_research=is_deep_research,
            )
            self._agents[conversation_id] = agent
            self._agent_configs[conversation_id] = (
                requested_provider,
                requested_model,
                is_deep_research,
            )
            return agent
        except Exception as e:
            logger.exception(
                "Failed to create agent",
                conversation_id=conversation_id,
                error=str(e),
            )
            raise

    def remove_agent(self, conversation_id: str) -> None:
        """Remove agent instance and any active background run for a conversation."""
        self._background_runner.cancel_run(conversation_id)
        self._agents.pop(conversation_id, None)
        for mode in (False, True):
            self._checkpointers.pop((conversation_id, mode), None)
            self._stores.pop((conversation_id, mode), None)
        self._agent_configs.pop(conversation_id, None)

    def _build_snapshot_from_state(
        self,
        conversation_id: str,
        run: BackgroundRun,
    ) -> dict[str, Any]:
        """Compatibility wrapper around snapshot state recovery."""
        return build_snapshot_from_state(
            agent=self._agents.get(conversation_id),
            conversation_id=conversation_id,
            run_snapshot=run.snapshot,
            logger=logger,
        )

    def start_background_run(
        self,
        conversation_id: str,
        message: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
        request_id: Optional[str] = None,
    ) -> BackgroundRun:
        return self._background_runner.start_background_run(
            conversation_id=conversation_id,
            message=message,
            model_provider=model_provider,
            model_name=model_name,
            is_deep_research=is_deep_research,
            request_id=request_id,
        )

    async def subscribe_to_run(
        self,
        conversation_id: str,
    ) -> AsyncGenerator[StreamEvent, None]:
        async for event in self._background_runner.subscribe_to_run(conversation_id):
            yield event

    def has_background_run(self, conversation_id: str) -> bool:
        return self._background_runner.has_background_run(conversation_id)

    async def stream_response(
        self,
        conversation_id: str,
        message: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> AsyncGenerator[StreamEvent, None]:
        """Backward-compatible direct event stream for tests and non-background use."""
        async for event in self._stream_agent_events(
            conversation_id=conversation_id,
            message=message,
            model_provider=model_provider,
            model_name=model_name,
            is_deep_research=is_deep_research,
        ):
            yield event

    async def _stream_agent_events(
        self,
        conversation_id: str,
        message: str,
        model_provider: Optional[str] = None,
        model_name: Optional[str] = None,
        is_deep_research: bool = False,
    ) -> AsyncGenerator[StreamEvent, None]:
        processor = StreamEventProcessor(
            get_or_create_agent=self._get_or_create_agent,
            resolve_runtime_settings=resolve_runtime_settings,
            run_research_stream=run_research_stream,
            run_research_async=run_research_async,
            heartbeat_interval_seconds=self.DEEP_RESEARCH_HEARTBEAT_INTERVAL_SECONDS,
            heartbeat_fallback_node=self.DEEP_RESEARCH_HEARTBEAT_FALLBACK_NODE,
            logger=logger,
        )
        async for event in processor.stream_agent_events(
            conversation_id=conversation_id,
            message=message,
            model_provider=model_provider,
            model_name=model_name,
            is_deep_research=is_deep_research,
        ):
            yield event

    def get_available_models(self) -> list[ModelInfo]:
        """Get list of available models."""
        models = []

        for name in ALIYUN_MODELS.keys():
            models.append(
                ModelInfo(
                    provider="aliyun",
                    name=name,
                    display_name=f"Aliyun {name}",
                    supports_thinking=name
                    in [
                        "qwen3.6-plus",
                        "kimi-k2.6",
                        "glm-5.1",
                        "deepseek-v4-pro",
                        "deepseek-v4-flash",
                    ],
                )
            )

        for _alias, full_name in OPENROUTER_MODELS.items():
            model_display = full_name.split("/")[-1]
            models.append(
                ModelInfo(
                    provider="openrouter",
                    name=full_name,
                    display_name=f"{model_display} (OpenRouter)",
                    supports_thinking=False,
                )
            )

        return models


_agent_service: Optional[AgentService] = None


def get_agent_service() -> AgentService:
    """Get the agent service singleton."""
    global _agent_service
    if _agent_service is None:
        _agent_service = AgentService()
    return _agent_service
