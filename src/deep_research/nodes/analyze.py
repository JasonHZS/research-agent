"""
Analyze Query Node

分析用户查询类型，决定是否需要前置探索（discover）阶段。
用于区分不同类型的研究任务，并路由到相应的处理流程。
"""

import json
from typing import Literal

from langchain_core.messages import get_buffer_string
from langchain_core.runnables import RunnableConfig
from langgraph.types import Command

from src.prompts import load_prompt
from src.utils.logging_config import get_logger

logger = get_logger(__name__)

from ..config import parse_deep_research_config
from ..state import AgentState
from ..structured_outputs import QueryAnalysis
from ..utils.llm import get_llm
from ..utils.state import get_state_value


async def analyze_query_node(
    state: AgentState,
    config: RunnableConfig,
) -> Command[Literal["discover", "plan_sections"]]:
    """
    分析查询类型，决定是否需要前置探索。

    识别查询类型：
    - list: "有哪些"类型，需要先发现所有实体
    - comparison: 对比分析
    - deep_dive: 深入研究单一主题
    - general: 一般性查询

    使用 Command API 返回，根据查询类型决定下一节点：
    - list 类型且需要前置探索 -> discover (先整体发现)
    - 其他类型 -> plan_sections (直接规划)
    """
    deep_config = parse_deep_research_config(config)

    llm = get_llm(deep_config.model_provider, deep_config.model_name)

    # 获取查询
    messages = get_state_value(state, "messages", [])
    query_text = get_buffer_string(messages) if messages else ""

    # 从模板加载分析 prompt
    analysis_prompt = load_prompt(
        "deep_research/analyze",
        query=query_text,
    )

    try:
        # 根据 provider 选择最合适的结构化输出方式
        if deep_config.model_provider == "aliyun":
            # DashScope 兼容模式：使用 response_format 参数（JSON Object 模式）
            # 很多 DashScope 模型不支持 function calling，但支持 JSON Object 模式
            # 参考: https://help.aliyun.com/zh/model-studio/qwen-structured-output
            llm_with_json = llm.bind(response_format={"type": "json_object"})
            response = await llm_with_json.ainvoke(analysis_prompt)

            # response_format 保证返回标准 JSON，直接解析并验证
            raw_result = json.loads(response.content)
            result = QueryAnalysis(**raw_result)
        else:
            # OpenAI / Anthropic：使用 with_structured_output（基于 function calling）
            # 这些 provider 原生支持 function calling，更可靠
            llm_with_output = llm.with_structured_output(QueryAnalysis)
            result = await llm_with_output.ainvoke(analysis_prompt)

        logger.info(
            "Query analyzed",
            query_type=result.query_type,
            output_format=result.output_format,
            needs_discovery=result.needs_discovery,
            discovery_target=result.discovery_target,
        )
        print(
            f"\n[Analyze]: 查询类型={result.query_type}, 输出格式={result.output_format}"
        )
        print(f"  需要前置探索: {result.needs_discovery}")
        if result.discovery_target:
            print(f"  发现目标: {result.discovery_target}")
        print()

        # 决定下一节点
        if result.needs_discovery and result.query_type == "list":
            next_node = "discover"
        else:
            next_node = "plan_sections"

        return Command(
            goto=next_node,
            update={
                "query_type": result.query_type,
                "output_format": result.output_format,
                "original_query": query_text,
            },
        )

    except Exception as e:
        logger.warning(
            "Query analysis failed, using defaults",
            error=str(e),
            error_type=type(e).__name__,
        )
        print(f"\n[Analyze]: 分析失败，使用默认值: {e}\n")
        # 回退到默认值
        return Command(
            goto="plan_sections",
            update={
                "query_type": "general",
                "output_format": "prose",
                "original_query": query_text,
            },
        )
