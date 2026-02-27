"""API Routes."""

from src.api.routes.chat import router as chat_router
from src.api.routes.feeds import router as feeds_router
from src.api.routes.models import router as models_router

__all__ = ["chat_router", "feeds_router", "models_router"]
