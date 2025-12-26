"""
Quick debug script for the first node (clarify_with_user).

It enables LangChain local debug logs and streams LangGraph events, then stops
after the clarify node finishes so you can inspect its output without running
the entire graph.
"""

import asyncio
import os
import uuid

from langchain_core.messages import HumanMessage
from langchain_core.runnables import RunnableConfig
from dotenv import load_dotenv

from src.deep_research.graph import build_deep_research_graph

TEST_QUERY = "帮我研究调研一下meta和快手在推荐系统结合生成式大语言模型的最新进展"


async def main() -> None:
    # Load environment variables from .env if present
    load_dotenv()
    # Basic API key check to avoid silent None outputs when auth is missing
    api_key = (
        os.getenv("ALIYUN_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    if not api_key:
        raise SystemExit(
            "Missing API key: set ALIYUN_API_KEY or DASHSCOPE_API_KEY "
            "(for qwen-compatible endpoints) or OPENAI_API_KEY."
        )

    # Enable verbose LC debug logs
    os.environ.setdefault("LANGCHAIN_DEBUG", "1")
    os.environ.setdefault("LANGCHAIN_DEBUG_LOG", "1")

    graph = build_deep_research_graph(model_provider="aliyun", model_name="qwen-max")

    config = {
        "configurable": {
            "thread_id": f"debug_{uuid.uuid4().hex[:8]}",
            "model_provider": "aliyun",
            "model_name": "qwen-max",
            "allow_clarification": True,
            "max_review_iterations": 2,
            "max_tool_calls_per_researcher": 10,
        }
    }

    initial_state = {"messages": [HumanMessage(content=TEST_QUERY)]}

    print("Streaming events (will stop after clarify_with_user completes)...\n")
    async for event in graph.astream_events(initial_state, config, version="v1"):
        name = event.get("name")
        if event["event"] == "on_chain_error":
            print(f"[{name}] error: {event}")
            break
        if event["event"] == "on_chain_end" and name == "clarify_with_user":
            output = event.get("data", {}).get("output")
            print(f"[{name}] output:\n{output}\n")
            break


if __name__ == "__main__":
    asyncio.run(main())
