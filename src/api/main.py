"""
FastAPI Application Entry Point

This module provides the FastAPI application for the research agent web API.

Usage:
    uvicorn src.api.main:app --reload --port 8000

Or with the CLI:
    python -m src.api.main
"""

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.api.routes import chat_router, conversations_router, models_router
from src.api.services.agent_service import get_agent_service
from src.api.services.db import init_database
from src.main import initialize_mcp_tools

# Load environment variables
load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - startup and shutdown events."""
    # Startup
    print("Initializing database...")
    await init_database()
    print("Database initialized.")

    # Initialize MCP tools (Hacker News)
    mcp_ctx = None
    try:
        print("Loading MCP tools (Hacker News)...")
        mcp_ctx = await initialize_mcp_tools()
        hn_count = len(mcp_ctx.hn_tools) if mcp_ctx and mcp_ctx.hn_tools else 0
        get_agent_service().set_mcp_tools(mcp_ctx.hn_tools if mcp_ctx else [])
        print(f"Loaded Hacker News MCP tools: {hn_count}")
    except Exception as e:
        print(f"⚠ Warning: Failed to load MCP tools: {e}")

    yield

    # Shutdown
    print("Shutting down...")
    if mcp_ctx:
        try:
            await mcp_ctx.cleanup()
        except Exception as e:
            print(f"⚠ Warning: MCP cleanup failed: {e}")


# Create FastAPI app
app = FastAPI(
    title="Research Agent API",
    description="Web API for the deep research agent with streaming support",
    version="0.1.0",
    lifespan=lifespan,
)

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

# Include routers
app.include_router(conversations_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(models_router, prefix="/api")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "research-agent-api"}


# Serve static files for frontend (in production)
# This is typically handled by a reverse proxy in production
# frontend_path = os.path.join(os.path.dirname(__file__), "../../frontend/out")
# if os.path.exists(frontend_path):
#     app.mount("/", StaticFiles(directory=frontend_path, html=True), name="frontend")


def main():
    """Run the API server."""
    import uvicorn

    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")

    uvicorn.run(
        "src.api.main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
