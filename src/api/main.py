"""
FastAPI Application Entry Point

This module provides the FastAPI application for the research agent web API.

Usage:
    uvicorn src.api.main:app --reload --port 8111

Or with the CLI:
    python -m src.api.main
"""

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import LoggingMiddleware
from src.api.routes import chat_router, feeds_router, models_router
from src.api.services.agent_service import get_agent_service
from src.config.settings import resolve_api_settings
from src.main import initialize_mcp_tools
from src.utils.logging_config import configure_logging, get_logger

# Load environment variables
load_dotenv()

# Initialize logging (must be called before creating loggers)
configure_logging()

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    logger.info("Starting Research Agent API", mode="ephemeral")

    # Initialize MCP tools (Hacker News)
    mcp_ctx = None
    try:
        logger.info("Loading MCP tools", server="hacker_news")
        mcp_ctx = await initialize_mcp_tools()
        hn_count = len(mcp_ctx.hn_tools) if mcp_ctx and mcp_ctx.hn_tools else 0
        get_agent_service().set_mcp_tools(mcp_ctx.hn_tools if mcp_ctx else [])
        logger.info("MCP tools loaded", server="hacker_news", tool_count=hn_count)
    except Exception as e:
        logger.warning("Failed to load MCP tools", error=str(e), exc_info=True)

    logger.info("API ready", persistence="ephemeral")

    yield

    # Shutdown
    logger.info("Shutting down API")
    if mcp_ctx:
        try:
            await mcp_ctx.cleanup()
            logger.debug("MCP cleanup completed")
        except Exception as e:
            logger.warning("MCP cleanup failed", error=str(e))


# Create FastAPI app
app = FastAPI(
    title="Research Agent API",
    description="Web API for the deep research agent with streaming support (ephemeral sessions)",
    version="0.2.0",
    lifespan=lifespan,
)

# Add logging middleware (must be added before other middleware for accurate timing)
app.add_middleware(LoggingMiddleware)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # Next.js dev server
        "http://127.0.0.1:3000",
        "http://localhost:5173",  # Vite dev server (if used)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers (no conversations router - ephemeral mode)
app.include_router(chat_router, prefix="/api")
app.include_router(feeds_router, prefix="/api")
app.include_router(models_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "research-agent-api", "mode": "ephemeral"}


def main():
    """Run the API server."""
    import uvicorn

    api_settings = resolve_api_settings()

    uvicorn.run(
        "src.api.main:app",
        host=api_settings.host,
        port=api_settings.port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
