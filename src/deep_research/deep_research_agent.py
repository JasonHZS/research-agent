"""
Deep Research Agent Implementation

This module implements the Deep Research graph using LangGraph StateGraph.
It provides a "Clarify -> Plan -> Retrieve -> Read -> Reflect" loop
that iteratively gathers information until evidence sufficiency is reached.

Key Features:
- Intent clarification with user interaction
- Section-based research planning
- Iterative retrieval with reflection
- Configurable max iterations
- Full tool chain reuse from main agent
"""

import json
import os
from typing import Any, Literal, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from langgraph.prebuilt import ToolNode

from src.agent.subagents import get_main_agent_tools
from src.config.deep_research_config import get_max_iterations
from src.prompts import load_prompt
from src.tools.arxiv_api import get_arxiv_paper_tool, search_arxiv_papers_tool
from src.tools.bocha_search import bocha_web_search_tool
from src.tools.github_search import github_search_tool
from src.tools.hf_blog import get_huggingface_blog_posts_tool
from src.tools.hf_daily_papers import get_huggingface_papers_tool
from src.tools.zyte_reader import get_zyte_article_list_tool

from .state import DeepResearchState


# =============================================================================
# LLM Configuration
# =============================================================================


def _get_llm(
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
) -> ChatOpenAI:
    """
    Get LLM instance for deep research nodes.

    Args:
        model_provider: LLM provider (aliyun, openai, anthropic).
        model_name: Specific model name.

    Returns:
        ChatOpenAI instance.
    """
    if model_provider == "aliyun":
        base_url = os.getenv(
            "ALIYUN_API_BASE_URL",
            "https://dashscope.aliyuncs.com/compatible-mode/v1",
        )
        api_key = os.getenv("ALIYUN_API_KEY") or os.getenv("DASHSCOPE_API_KEY")
        return ChatOpenAI(
            model=model_name or "qwen-max",
            api_key=api_key,
            base_url=base_url,
        )
    elif model_provider == "openai":
        return ChatOpenAI(model=model_name or "gpt-4o")
    elif model_provider == "anthropic":
        # For Anthropic, we still use ChatOpenAI with compatible endpoint
        # or you can use ChatAnthropic
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(model=model_name or "claude-sonnet-4-20250514")
    else:
        raise ValueError(f"Unknown provider: {model_provider}")


# =============================================================================
# Node Functions
# =============================================================================


async def clarify_intent_node(
    state: DeepResearchState,
    llm: ChatOpenAI,
) -> dict:
    """
    Clarify user intent by asking follow-up questions if needed.

    This node analyzes the user's query and determines if clarification is needed.
    If the query is too broad or ambiguous, it generates a clarification question.
    """
    # Build conversation history for the prompt
    history = ""
    if state.clarification_history:
        history = "\n".join(state.clarification_history)

    # If user just answered a question, add it to history
    if state.user_answer:
        history += f"\n用户回答: {state.user_answer}"

    # Load and render the clarify prompt
    prompt_text = load_prompt(
        "deep_research/clarify",
        query=state.original_query,
        conversation_history=history if history else None,
    )

    # Call LLM
    response = await llm.ainvoke([SystemMessage(content=prompt_text)])
    content = response.content

    # Parse JSON response
    try:
        # Extract JSON from markdown code block if present
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        result = json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        # If parsing fails, assume query is clear
        result = {"is_clear": True, "refined_query": state.original_query}

    if result.get("is_clear", False):
        return {
            "is_clarified": True,
            "clarified_query": result.get("refined_query", state.original_query),
            "pending_question": None,
            "user_answer": None,
        }
    else:
        # Need clarification
        question = result.get("clarification_question", "请问您能更具体地描述您的研究需求吗？")
        new_history = state.clarification_history.copy()
        new_history.append(f"系统询问: {question}")

        return {
            "is_clarified": False,
            "pending_question": question,
            "clarification_history": new_history,
            "user_answer": None,
        }


async def plan_sections_node(
    state: DeepResearchState,
    llm: ChatOpenAI,
) -> dict:
    """
    Generate a research plan with sections based on the clarified query.
    """
    prompt_text = load_prompt(
        "deep_research/plan",
        query=state.clarified_query,
    )

    response = await llm.ainvoke([SystemMessage(content=prompt_text)])
    content = response.content

    # Parse JSON response
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        result = json.loads(json_str)
        sections = result.get("sections", [])
    except (json.JSONDecodeError, IndexError):
        # Fallback: create a simple single-section plan
        sections = [
            {
                "title": "主要研究内容",
                "description": state.clarified_query,
                "search_queries": [state.clarified_query],
            }
        ]

    # Extract initial search queries from all sections
    all_queries = []
    for section in sections:
        all_queries.extend(section.get("search_queries", []))

    return {
        "sections": sections,
        "current_queries": all_queries[:5],  # Limit initial queries
        "iteration_count": 0,
    }


async def retrieve_node(
    state: DeepResearchState,
    tools: list,
    llm: ChatOpenAI,
) -> dict:
    """
    Execute search queries using available tools.

    This node uses the LLM to decide which tools to call based on the queries.
    """
    if not state.current_queries:
        return {"search_results": []}

    # Build a prompt for the LLM to decide tool usage
    queries_text = "\n".join([f"- {q}" for q in state.current_queries])

    system_prompt = f"""你是一个 AI 研究检索专家。根据以下搜索查询，调用合适的工具获取信息。

## 待搜索的查询
{queries_text}

## 可用工具
- search_arxiv_papers_tool: 搜索 ArXiv 论文
- get_arxiv_paper_tool: 获取特定 ArXiv ID 的论文详情
- get_huggingface_papers_tool: 获取 HuggingFace 每日热门论文
- get_huggingface_blog_posts_tool: 获取 HuggingFace 博客文章列表
- get_zyte_article_list_tool: 获取博客网站的文章列表
- github_search_tool: 搜索 GitHub 仓库
- bocha_web_search_tool: 通用网络搜索（仅作为兜底）
- Hacker News 工具: 获取 HN 热门讨论

## 任务
为每个查询选择最合适的工具并执行搜索。优先使用高质量信源（ArXiv > HuggingFace > GitHub > 通用搜索）。
"""

    # Bind tools to LLM
    llm_with_tools = llm.bind_tools(tools)

    # Create message and get tool calls
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"请为以下查询执行搜索: {queries_text}"),
    ]

    response = await llm_with_tools.ainvoke(messages)

    # Execute tool calls
    results = []
    if hasattr(response, "tool_calls") and response.tool_calls:
        tool_node = ToolNode(tools)
        tool_messages = await tool_node.ainvoke(
            {"messages": [response]},
        )
        for msg in tool_messages.get("messages", []):
            if hasattr(msg, "content") and msg.content:
                results.append(msg.content)

    # Track visited sources (simplified - just track queries for now)
    new_sources = state.current_queries.copy()

    return {
        "search_results": results,
        "visited_sources": new_sources,
        "messages": messages + [response],
    }


async def read_node(
    state: DeepResearchState,
    llm: ChatOpenAI,
) -> dict:
    """
    Process and summarize search results.

    This node extracts key information from raw search results.
    In a full implementation, this would call the content-reader-agent
    for URLs that need deep reading.
    """
    if not state.search_results:
        return {"gathered_info": []}

    # Combine all search results
    combined_results = "\n\n---\n\n".join(state.search_results)

    # Use LLM to extract key findings
    summary_prompt = f"""请从以下搜索结果中提取关键信息，形成结构化的研究笔记。

## 研究问题
{state.clarified_query}

## 搜索结果
{combined_results[:15000]}  # Limit context length

## 输出要求
1. 提取与研究问题相关的关键发现
2. 标注信息来源（论文标题、URL 等）
3. 忽略无关或重复的信息
4. 保持客观，不添加主观评价

请直接输出提取的关键信息（Markdown 格式）：
"""

    response = await llm.ainvoke([HumanMessage(content=summary_prompt)])

    return {
        "gathered_info": [response.content],
        "search_results": [],  # Clear after processing
    }


async def reflect_node(
    state: DeepResearchState,
    llm: ChatOpenAI,
) -> dict:
    """
    Reflect on gathered information and decide whether to continue.

    This node evaluates if the collected information is sufficient
    to write a quality report, or if more research is needed.
    """
    # Format sections for prompt
    sections_text = json.dumps(state.sections, ensure_ascii=False, indent=2)

    # Format gathered info
    gathered_text = "\n\n---\n\n".join(state.gathered_info)

    prompt_text = load_prompt(
        "deep_research/reflect",
        query=state.clarified_query,
        sections=sections_text,
        gathered_info=gathered_text,
        iteration_count=state.iteration_count + 1,
        max_iterations=state.max_iterations,
    )

    response = await llm.ainvoke([SystemMessage(content=prompt_text)])
    content = response.content

    # Parse JSON response
    try:
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0].strip()
        else:
            json_str = content.strip()

        result = json.loads(json_str)
    except (json.JSONDecodeError, IndexError):
        # If parsing fails, check iteration count
        result = {
            "is_sufficient": state.iteration_count + 1 >= state.max_iterations,
            "next_queries": [],
        }

    # Force stop if max iterations reached
    is_sufficient = result.get("is_sufficient", False)
    if state.iteration_count + 1 >= state.max_iterations:
        is_sufficient = True

    return {
        "is_sufficient": is_sufficient,
        "current_queries": result.get("next_queries", [])[:3],
        "iteration_count": state.iteration_count + 1,
    }


async def write_report_node(
    state: DeepResearchState,
    llm: ChatOpenAI,
) -> dict:
    """
    Generate the final research report.
    """
    # Format sections for prompt
    sections_text = json.dumps(state.sections, ensure_ascii=False, indent=2)

    # Format gathered info
    gathered_text = "\n\n---\n\n".join(state.gathered_info)

    prompt_text = load_prompt(
        "deep_research/report",
        query=state.clarified_query,
        sections=sections_text,
        gathered_info=gathered_text,
    )

    response = await llm.ainvoke([SystemMessage(content=prompt_text)])

    return {"final_report": response.content}


# =============================================================================
# Graph Construction
# =============================================================================


def _get_all_tools(hn_mcp_tools: Optional[list] = None) -> list:
    """
    Assemble all tools for the retrieve node.

    This mirrors the tool setup in research_agent.py.
    """
    all_tools = [
        get_huggingface_papers_tool,
        get_huggingface_blog_posts_tool,
        get_arxiv_paper_tool,
        search_arxiv_papers_tool,
        get_zyte_article_list_tool,
        bocha_web_search_tool,
        github_search_tool,
    ]

    # Add HN MCP tools
    hn_main_tools = get_main_agent_tools(hn_mcp_tools)
    if hn_main_tools:
        all_tools.extend(hn_main_tools)

    return all_tools


def build_deep_research_graph(
    hn_mcp_tools: Optional[list] = None,
    model_provider: str = "aliyun",
    model_name: Optional[str] = None,
    max_iterations: Optional[int] = None,
):
    """
    Build the Deep Research StateGraph.

    Args:
        hn_mcp_tools: Hacker News MCP tools from main.py.
        model_provider: LLM provider.
        model_name: Specific model name.
        max_iterations: Maximum research iterations (default from config).

    Returns:
        Compiled StateGraph.
    """
    # Get LLM
    llm = _get_llm(model_provider, model_name)

    # Get all tools
    tools = _get_all_tools(hn_mcp_tools)

    # Resolve max iterations
    resolved_max_iterations = get_max_iterations(max_iterations)

    # Create graph
    workflow = StateGraph(DeepResearchState)

    # Define node wrappers that inject dependencies
    async def clarify_node_wrapper(state: DeepResearchState):
        return await clarify_intent_node(state, llm)

    async def plan_node_wrapper(state: DeepResearchState):
        return await plan_sections_node(state, llm)

    async def retrieve_node_wrapper(state: DeepResearchState):
        return await retrieve_node(state, tools, llm)

    async def read_node_wrapper(state: DeepResearchState):
        return await read_node(state, llm)

    async def reflect_node_wrapper(state: DeepResearchState):
        return await reflect_node(state, llm)

    async def report_node_wrapper(state: DeepResearchState):
        return await write_report_node(state, llm)

    # Add nodes
    workflow.add_node("clarify", clarify_node_wrapper)
    workflow.add_node("plan", plan_node_wrapper)
    workflow.add_node("retrieve", retrieve_node_wrapper)
    workflow.add_node("read", read_node_wrapper)
    workflow.add_node("reflect", reflect_node_wrapper)
    workflow.add_node("report", report_node_wrapper)

    # Set entry point
    workflow.set_entry_point("clarify")

    # Define conditional edge: clarify -> plan or back to clarify (needs user input)
    def check_clarified(state: DeepResearchState) -> Literal["plan", "__interrupt__"]:
        if state.is_clarified:
            return "plan"
        # If not clarified, we need user input - interrupt the graph
        return "__interrupt__"

    workflow.add_conditional_edges(
        "clarify",
        check_clarified,
        {"plan": "plan", "__interrupt__": END},
    )

    # Linear edges
    workflow.add_edge("plan", "retrieve")
    workflow.add_edge("retrieve", "read")
    workflow.add_edge("read", "reflect")

    # Conditional edge: reflect -> report or back to retrieve
    def check_sufficient(state: DeepResearchState) -> Literal["report", "retrieve"]:
        if state.is_sufficient:
            return "report"
        return "retrieve"

    workflow.add_conditional_edges(
        "reflect",
        check_sufficient,
        {"report": "report", "retrieve": "retrieve"},
    )

    # End after report
    workflow.add_edge("report", END)

    # Compile with interrupt capability
    return workflow.compile()


# =============================================================================
# Helper Functions for Running
# =============================================================================


async def run_deep_research(
    query: str,
    graph,
    max_iterations: int = 5,
    on_clarify_question: Optional[callable] = None,
) -> str:
    """
    Run the deep research graph with human-in-the-loop for clarification.

    Args:
        query: User's research query.
        graph: Compiled deep research graph.
        max_iterations: Maximum iterations.
        on_clarify_question: Callback function to get user's answer to clarification.
                            Signature: async (question: str) -> str

    Returns:
        Final research report.
    """
    # Initial state
    state = DeepResearchState(
        original_query=query,
        max_iterations=max_iterations,
    )

    config = {"configurable": {"thread_id": "deep_research"}}

    # Run with potential interrupts for clarification
    current_state = state

    while True:
        # Run the graph
        result = await graph.ainvoke(current_state.model_dump(), config)

        # Check if we need clarification
        if result.get("pending_question") and not result.get("is_clarified"):
            if on_clarify_question:
                # Get user's answer
                answer = await on_clarify_question(result["pending_question"])
                # Update state with answer and continue
                current_state = DeepResearchState(**result)
                current_state.user_answer = answer
                current_state.pending_question = None
            else:
                # No callback, skip clarification
                current_state = DeepResearchState(**result)
                current_state.is_clarified = True
                current_state.clarified_query = current_state.original_query
        else:
            # Graph completed
            break

    return result.get("final_report", "")
