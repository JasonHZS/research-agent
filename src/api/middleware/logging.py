"""
Request Logging Middleware

Provides request tracing and automatic request/response logging for FastAPI.

Features:
- Generates unique request_id for each request
- Binds request_id to structlog context for automatic inclusion in all logs
- Logs request details (method, path, status code, duration)
- Clears context after request to prevent leakage
"""

import time
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from src.utils.logging_config import bind_context, clear_context, get_logger

logger = get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that adds request tracing and logging to all HTTP requests.

    For each request:
    1. Generates a unique request_id
    2. Binds request_id to structlog context
    3. Logs request start
    4. Processes the request
    5. Logs request completion with duration and status
    6. Clears context to prevent leakage
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request with logging and tracing."""
        # Generate unique request ID
        request_id = str(uuid.uuid4())[:8]

        # Bind context for all logs during this request
        bind_context(request_id=request_id)

        # Extract request info
        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "unknown"

        # Log request start (debug level to reduce noise)
        logger.debug(
            "Request started",
            method=method,
            path=path,
            client_ip=client_ip,
        )

        # Track timing
        start_time = time.perf_counter()

        try:
            # Process the request
            response = await call_next(request)

            # Calculate duration
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log request completion
            log_method = logger.info if response.status_code < 400 else logger.warning
            log_method(
                "Request completed",
                method=method,
                path=path,
                status_code=response.status_code,
                duration_ms=round(duration_ms, 2),
            )

            # Add request_id to response headers for client-side tracing
            response.headers["X-Request-ID"] = request_id

            return response

        except Exception as e:
            # Calculate duration even on error
            duration_ms = (time.perf_counter() - start_time) * 1000

            # Log the exception
            logger.exception(
                "Request failed with exception",
                method=method,
                path=path,
                duration_ms=round(duration_ms, 2),
                error=str(e),
            )
            raise

        finally:
            # Always clear context to prevent leakage to next request
            clear_context()
