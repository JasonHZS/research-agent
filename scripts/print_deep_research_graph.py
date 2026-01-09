#!/usr/bin/env python3
"""
Print Deep Research Graph Structure

This script builds the Deep Research graph and prints its structure
in various formats (ASCII, Mermaid, summary).

根据官方文档：
- 类型注解是必须的：使用 Command[Literal["node_a", "node_b"]] 返回类型注解，告诉 LangGraph 这个节点可以路由到哪些节点。我们修复后，边从 4 条增加到 7 条。
- Send API 的限制：plan_sections 使用 Send 动态派发到 researcher，这种动态派发在静态分析中没有对应的边表示。因此 researcher -> aggregate -> review -> final_report 整条链都显示不出来（因为 researcher 没有入边）。
- 实际的静态边：workflow.add_edge("researcher", "aggregate") 这些边在代码里存在，但由于 researcher 是个"孤岛节点"（没有静态入边），渲染时被忽略了。

    python scripts/print_deep_research_graph.py [--format FORMAT] [--output FILE]

Examples:
    # Print summary (default)
    python scripts/print_deep_research_graph.py

    # Print Mermaid diagram
    python scripts/print_deep_research_graph.py --format mermaid

    # Print ASCII representation
    python scripts/print_deep_research_graph.py --format ascii

    # Save Mermaid diagram to file
    python scripts/print_deep_research_graph.py --format mermaid --output graph.md
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv


def get_graph():
    """Build and return the Deep Research graph."""
    from src.deep_research.graph import build_deep_research_graph

    # Build the graph with empty tools (we only need the structure)
    graph = build_deep_research_graph(hn_mcp_tools=[])
    return graph


def print_ascii(graph) -> str:
    """Print ASCII representation of the graph."""
    try:
        compiled = graph.get_graph()
        return compiled.draw_ascii()
    except Exception as e:
        return f"Error generating ASCII: {e}"


def print_mermaid(graph) -> str:
    """Generate Mermaid diagram of the graph."""
    try:
        compiled = graph.get_graph()
        return compiled.draw_mermaid()
    except Exception as e:
        return f"Error generating Mermaid: {e}"


def print_summary(graph) -> str:
    """Print a summary of graph structure."""
    lines = []
    compiled = graph.get_graph()

    nodes = list(compiled.nodes.keys())
    edges = list(compiled.edges)

    lines.append("=" * 60)
    lines.append("DEEP RESEARCH GRAPH SUMMARY")
    lines.append("=" * 60)

    lines.append(f"\nNodes ({len(nodes)}):")
    for node in nodes:
        lines.append(f"  • {node}")

    lines.append(f"\nStatic Edges ({len(edges)}):")
    if edges:
        for edge in edges:
            # Handle different edge formats
            if hasattr(edge, "source") and hasattr(edge, "target"):
                lines.append(f"  • {edge.source} → {edge.target}")
            elif isinstance(edge, (tuple, list)) and len(edge) >= 2:
                lines.append(f"  • {edge[0]} → {edge[1]}")
            else:
                lines.append(f"  • {edge}")
    else:
        lines.append("  (All routing via Command API)")

    lines.append("\nNote: Most routing uses Command API (dynamic, not shown in static analysis).")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Print Deep Research graph structure",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument(
        "--format",
        "-f",
        choices=["ascii", "mermaid", "summary", "all"],
        default="summary",
        help="Output format (default: summary)",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=str,
        default=None,
        help="Save output to file (optional)",
    )

    args = parser.parse_args()

    # Load environment variables (might be needed for some imports)
    load_dotenv()

    print("Building Deep Research graph...")
    graph = get_graph()
    print("Graph built successfully!\n")

    # Generate output based on format
    if args.format == "ascii":
        output = print_ascii(graph)
    elif args.format == "mermaid":
        output = print_mermaid(graph)
    elif args.format == "summary":
        output = print_summary(graph)
    elif args.format == "all":
        sections = [
            print_summary(graph),
            "\n\n" + "=" * 60,
            "ASCII REPRESENTATION",
            "=" * 60 + "\n",
            print_ascii(graph),
            "\n\n" + "=" * 60,
            "MERMAID DIAGRAM",
            "=" * 60 + "\n",
            print_mermaid(graph),
        ]
        output = "\n".join(sections)

    # Print or save output
    print(output)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output)
        print(f"\n✓ Output saved to: {output_path}")


if __name__ == "__main__":
    main()
