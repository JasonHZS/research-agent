"""
Full deep-research graph event tracer.

Streams LangGraph events and prints each node's output to help debug where
the pipeline drops data. Stops after final_report_generation finishes.
"""

import asyncio
import os
import uuid
from typing import Any

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage

from src.deep_research.graph import build_deep_research_graph

TEST_QUERY = "帮我研究调研一下meta和快手在推荐系统结合生成式大语言模型的最新进展"


def _safe_trim(value: Any, limit: int = 800) -> str:
    """Return a trimmed string representation for logging."""
    text = ""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        text = repr(value)
    return text if len(text) <= limit else text[:limit] + "...[trimmed]"


async def main() -> None:
    load_dotenv()

    # Basic API key check
    api_key = (
        os.getenv("ALIYUN_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not api_key:
        raise SystemExit(
            "Missing API key: set ALIYUN_API_KEY/DASHSCOPE_API_KEY or OPENAI_API_KEY."
        )

    graph = build_deep_research_graph(model_provider="aliyun", model_name="qwen3.5-plus")
    config = {
        "configurable": {
            "thread_id": f"debug_full_{uuid.uuid4().hex[:8]}",
            "model_provider": "aliyun",
            "model_name": "qwen3.5-plus",
            "allow_clarification": True,
            "max_iterations": 2,
            "max_tool_calls": 10,
        }
    }
    initial_state = {"messages": [HumanMessage(content=TEST_QUERY)]}

    print("Streaming all node events (will stop after final_report_generation)...\n")
    async for event in graph.astream_events(initial_state, config, version="v1"):
        name = event.get("name")
        ev_type = event["event"]

        if ev_type == "on_chain_error":
            print(f"[{name}] ERROR: {event.get('error') or event}")
            break

        if ev_type == "on_chain_end":
            output = event.get("data", {}).get("output")
            print(f"[{name}] output: {_safe_trim(output)}\n")
            if name == "final_report_generation":
                break


if __name__ == "__main__":
    asyncio.run(main())
