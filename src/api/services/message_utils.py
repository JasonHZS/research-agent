"""Pure utility functions for message processing, tool result formatting, and sanitization."""

import json
from typing import Any

import httpcore
import httpx


def format_tool_result(content: Any, max_len: int = 500) -> str:
    """Normalize tool result to a short, display-friendly string."""
    if content is None:
        return ""
    if isinstance(content, str):
        text = content
    else:
        try:
            text = json.dumps(content, ensure_ascii=False, default=str)
        except TypeError:
            text = str(content)
    return text[:max_len] if max_len and len(text) > max_len else text


def is_error_result(result: str) -> bool:
    """Check if a tool result indicates an error.

    Uses tight, position-aware matching to avoid false positives on benign
    text that merely *mentions* error words (e.g. "2 papers not found in
    arXiv" or a code snippet discussing `try/except`). Only the first
    ~200 chars are inspected so a long body that happens to contain
    "Error: ..." deep inside doesn't flip an otherwise successful result.
    """
    if not result:
        return False

    head = result.strip().lower()[:200]
    if not head:
        return False

    prefix_indicators = (
        "error",
        "failed",
        "exception",
        "traceback",
        "timeout",
    )
    if any(head.startswith(p) for p in prefix_indicators):
        return True

    marker_indicators = (
        "error:",
        "exception:",
        "failed:",
        "[error]",
        "connection refused",
        "rate limit exceeded",
        "401 unauthorized",
        "403 forbidden",
    )
    return any(marker in head for marker in marker_indicators)


def is_stream_disconnect_error(exc: Exception) -> bool:
    """Return True when upstream closes streaming response early."""
    if isinstance(exc, (httpx.RemoteProtocolError, httpcore.RemoteProtocolError)):
        return True

    message = str(exc).lower()
    if "incomplete chunked read" in message or "peer closed connection" in message:
        return True

    cause = getattr(exc, "__cause__", None)
    if cause and isinstance(cause, (httpx.RemoteProtocolError, httpcore.RemoteProtocolError)):
        return True

    return False


_SENSITIVE_KEYS = ["key", "token", "secret", "password", "credential", "auth"]


def sanitize_tool_args(args: Any) -> Any:
    """Filter sensitive information from tool arguments before logging."""
    if not args:
        return args

    if isinstance(args, dict):
        sanitized = {}
        for k, v in args.items():
            if any(s in k.lower() for s in _SENSITIVE_KEYS):
                sanitized[k] = "***REDACTED***"
            else:
                sanitized[k] = v
        return sanitized

    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            if isinstance(parsed, dict):
                sanitized = {}
                for k, v in parsed.items():
                    if any(s in k.lower() for s in _SENSITIVE_KEYS):
                        sanitized[k] = "***REDACTED***"
                    else:
                        sanitized[k] = v
                return json.dumps(sanitized)
        except (json.JSONDecodeError, TypeError):
            pass

    return args


def extract_messages_recursive(data: Any, max_depth: int = 5) -> list:
    """
    Recursively extract messages from nested node data.

    Handles subgraph updates where data may be nested like:
    {"researcher": {"researcher": {"researcher_messages": [...]}}}

    Looks for these fields:
    - messages: standard LangGraph messages
    - researcher_messages: from researcher subgraph
    - tool_calls_log: from clarify node's internal tool calls
    """
    if max_depth <= 0 or data is None:
        return []

    if hasattr(data, "value"):
        data = data.value

    if not isinstance(data, dict):
        return []

    all_messages: list = []
    message_fields = ["messages", "researcher_messages", "tool_calls_log"]

    for key, value in data.items():
        if hasattr(value, "value"):
            value = value.value

        if key in message_fields:
            if isinstance(value, (list, tuple)):
                all_messages.extend(value)
        elif isinstance(value, dict):
            all_messages.extend(extract_messages_recursive(value, max_depth - 1))

    return all_messages
