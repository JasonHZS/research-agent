"""Models route for listing available LLM models."""

from fastapi import APIRouter

from src.api.schemas.chat import ModelInfo, ModelsResponse
from src.api.services.agent_service import get_agent_service

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=ModelsResponse)
async def list_models():
    """List all available models."""
    agent_service = get_agent_service()
    models = agent_service.get_available_models()

    return ModelsResponse(
        models=models,
        current_provider="aliyun",
        current_model="qwen-max",
    )
