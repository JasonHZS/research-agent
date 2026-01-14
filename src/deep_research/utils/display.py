"""
Deep Research Display Utilities

提供深度研究模式的工具调用打印功能。
格式与普通模式 (stream_display.py) 保持一致。
"""

from typing import Optional


# 不需要截断的关键参数
FULL_DISPLAY_KEYS = {"description", "query", "prompt"}


def format_tool_args(args: dict, verbose: bool = False) -> str:
    """
    格式化工具参数。

    Args:
        args: 工具参数字典
        verbose: 是否显示详细参数

    Returns:
        格式化后的参数字符串
    """
    if not args:
        return ""

    parts = []
    for k, v in args.items():
        if isinstance(v, str):
            # verbose 模式显示更多字符
            max_len = 50 if verbose else 30
            if k not in FULL_DISPLAY_KEYS and len(v) > max_len:
                v = v[: max_len - 3] + "..."
            parts.append(f'{k}="{v}"')
        elif isinstance(v, (int, float, bool)):
            parts.append(f"{k}={v}")
        elif isinstance(v, list):
            parts.append(f"{k}=[{len(v)} items]")
        elif isinstance(v, dict):
            parts.append(f"{k}={{...}}")
    return ", ".join(parts)


def render_tool_calls(
    tool_calls: list[dict],
    verbose: bool = False,
    section_title: Optional[str] = None,
) -> None:
    """
    打印工具调用信息。

    格式：
    ```
    ┌─ Tool Calls [章节标题]
    │  🔧 tool_name(arg1="value", arg2="value")
    │  🔧 another_tool(...)
    └─
    ```

    Args:
        tool_calls: 工具调用列表，每个元素是包含 name 和 args 的字典
        verbose: 是否显示详细参数
        section_title: 当前章节标题（用于识别并行任务）
    """
    header = "Tool Calls"
    if section_title:
        header = f"Tool Calls [{section_title}]"

    print(f"\n┌─ {header}")
    for tc in tool_calls:
        name = tc.get("name", "unknown")
        args = tc.get("args", {})
        args_str = format_tool_args(args, verbose)
        print(f"│  🔧 {name}({args_str})")
    print("└─")
