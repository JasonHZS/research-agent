"""
Minimal clarify node runner that loads .env and prints the structured output.
Useful to verify the clarify node returns a question when allow_clarification=True.
"""

import asyncio
import uuid

from dotenv import load_dotenv
from langchain_core.messages import AIMessage, HumanMessage

from src.deep_research.graph import build_deep_research_graph


async def main() -> None:
    load_dotenv()
    graph = build_deep_research_graph()
    config = {
        "configurable": {
            "thread_id": f"clarify_{uuid.uuid4().hex[:8]}",
            "allow_clarification": True,
        }
    }
    query = "帮我研究调研一下meta和快手在推荐系统结合生成式大语言模型的最新进展"
    result = await graph.ainvoke({"messages": [HumanMessage(content=query)]}, config)

    # 检查澄清结果
    messages = result.get("messages", [])
    final_report = result.get("final_report", "")

    if not final_report and messages:
        last_message = messages[-1]
        if isinstance(last_message, AIMessage):
            print("✅ 收到澄清问题:")
            print(f"   {last_message.content}")
        else:
            print("❌ 最后一条消息不是 AIMessage")
            print(f"   类型: {type(last_message)}")
    elif final_report:
        print("⚠️ 图已完成（未触发澄清），final_report 已生成")
    else:
        print("❓ 未知状态")
        print(f"   messages: {messages}")


if __name__ == "__main__":
    asyncio.run(main())
