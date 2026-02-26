"""Models route for listing available LLM models."""

from fastapi import APIRouter

from src.api.schemas.chat import ModelInfo, ModelsResponse
from src.api.services.agent_service import get_agent_service
from src.config.settings import get_app_settings, get_default_model_for_provider

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelsResponse)
async def list_models():
    """List all available models."""
    agent_service = get_agent_service()
    models = agent_service.get_available_models()
    settings = get_app_settings()

    return ModelsResponse(
        models=models,
        current_provider=settings.llm.provider,
        current_model=settings.llm.model_name
        or get_default_model_for_provider(settings.llm.provider),
    )
