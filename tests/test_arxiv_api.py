"""
Test script for ArXiv API Tools

This script tests the native ArXiv API tools for searching and fetching papers.

Usage:
    # Run all tests
    python tests/test_arxiv_api.py

    # Test with specific paper
    python tests/test_arxiv_api.py 2402.02716

    # Test search
    python tests/test_arxiv_api.py --search "LLM agents"
"""

import os
import sys

# Ensure the project root is in python path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.tools.arxiv_api import (
    fetch_arxiv_paper,
    get_arxiv_paper_tool,
    search_arxiv,
    search_arxiv_papers_tool,
)


def test_fetch_single_paper():
    """Test fetching a single paper by ArXiv ID."""
    print("=" * 60)
    print("Test 1: Fetch Single Paper")
    print("=" * 60)

    # Test with a known paper ID
    arxiv_id = "2402.02716"
    print(f"\nFetching paper: {arxiv_id}")

    try:
        result = get_arxiv_paper_tool.invoke({"arxiv_id": arxiv_id})
        print("\n--- Result (first 500 chars) ---")
        print(result[:500] + "..." if len(result) > 500 else result)
        print("--- End Result ---")

        if result.startswith("Error"):
            print("\n[FAILED] Error occurred")
            return False
        else:
            print("\n[PASSED]")
            return True
    except Exception as e:
        print(f"\n[FAILED] Exception: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_fetch_paper_from_url():
    """Test fetching a paper using full ArXiv URL."""
    print("\n" + "=" * 60)
    print("Test 2: Fetch Paper from URL")
    print("=" * 60)

    arxiv_url = "https://arxiv.org/abs/2402.02716v1"
    print(f"\nFetching paper from URL: {arxiv_url}")

    try:
        result = get_arxiv_paper_tool.invoke({"arxiv_id": arxiv_url})
        print("\n--- Result (first 500 chars) ---")
        print(result[:500] + "..." if len(result) > 500 else result)
        print("--- End Result ---")

        if result.startswith("Error"):
            print("\n[FAILED] Error occurred")
            return False
        else:
            print("\n[PASSED]")
            return True
    except Exception as e:
        print(f"\n[FAILED] Exception: {e}")
        return False


def test_search_papers():
    """Test searching for papers."""
    print("\n" + "=" * 60)
    print("Test 3: Search Papers")
    print("=" * 60)

    query = "LLM agents"
    print(f"\nSearching for: {query}")

    try:
        result = search_arxiv_papers_tool.invoke({"query": query, "max_results": 3})
        print("\n--- Result (first 1000 chars) ---")
        print(result[:1000] + "..." if len(result) > 1000 else result)
        print("--- End Result ---")

        if result.startswith("Error"):
            print("\n[FAILED] Error occurred")
            return False
        elif "No papers found" in result:
            print("\n[WARNING] No papers found")
            return True
        else:
            print("\n[PASSED]")
            return True
    except Exception as e:
        print(f"\n[FAILED] Exception: {e}")
        return False


def test_search_with_category():
    """Test searching with category filter."""
    print("\n" + "=" * 60)
    print("Test 4: Search with Category Filter")
    print("=" * 60)

    query = "cat:cs.AI AND transformer"
    print(f"\nSearching with category: {query}")

    try:
        result = search_arxiv_papers_tool.invoke(
            {"query": query, "max_results": 3, "sort_by": "submittedDate"}
        )
        print("\n--- Result (first 1000 chars) ---")
        print(result[:1000] + "..." if len(result) > 1000 else result)
        print("--- End Result ---")

        if result.startswith("Error"):
            print("\n[FAILED] Error occurred")
            return False
        else:
            print("\n[PASSED]")
            return True
    except Exception as e:
        print(f"\n[FAILED] Exception: {e}")
        return False


def test_invalid_paper_id():
    """Test handling of invalid paper ID."""
    print("\n" + "=" * 60)
    print("Test 5: Invalid Paper ID")
    print("=" * 60)

    arxiv_id = "0000.00000"
    print(f"\nFetching invalid paper: {arxiv_id}")

    try:
        result = get_arxiv_paper_tool.invoke({"arxiv_id": arxiv_id})
        print("\n--- Result ---")
        print(result)
        print("--- End Result ---")

        # Should return an error message, not crash
        if "Error" in result or "not found" in result.lower():
            print("\n[PASSED] Correctly handled invalid ID")
            return True
        else:
            print("\n[FAILED] Should have returned error for invalid ID")
            return False
    except Exception as e:
        print(f"\n[FAILED] Unexpected exception: {e}")
        return False


def test_helper_functions():
    """Test the helper functions directly."""
    print("\n" + "=" * 60)
    print("Test 6: Helper Functions")
    print("=" * 60)

    print("\nTesting fetch_arxiv_paper()...")
    try:
        paper = fetch_arxiv_paper("2402.02716")
        assert paper["arxiv_id"] == "2402.02716"
        assert "title" in paper
        assert "authors" in paper
        assert isinstance(paper["authors"], list)
        print(f"  Title: {paper['title'][:50]}...")
        print(f"  Authors: {len(paper['authors'])} author(s)")
        print("  [PASSED]")
    except Exception as e:
        print(f"  [FAILED] {e}")
        return False

    print("\nTesting search_arxiv()...")
    try:
        papers = search_arxiv("machine learning", max_results=3)
        assert isinstance(papers, list)
        assert len(papers) <= 3
        print(f"  Found {len(papers)} papers")
        print("  [PASSED]")
    except Exception as e:
        print(f"  [FAILED] {e}")
        return False

    return True


def run_all_tests():
    """Run all tests and report results."""
    print("\n" + "=" * 60)
    print("ArXiv API Tools Test Suite")
    print("=" * 60)

    results = {
        "Fetch Single Paper": test_fetch_single_paper(),
        "Fetch from URL": test_fetch_paper_from_url(),
        "Search Papers": test_search_papers(),
        "Search with Category": test_search_with_category(),
        "Invalid Paper ID": test_invalid_paper_id(),
        "Helper Functions": test_helper_functions(),
    }

    print("\n" + "=" * 60)
    print("Test Results Summary")
    print("=" * 60)

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for name, result in results.items():
        status = "[PASS]" if result else "[FAIL]"
        print(f"  {status} {name}")

    print(f"\nTotal: {passed}/{total} tests passed")

    return passed == total


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--search":
            query = sys.argv[2] if len(sys.argv) > 2 else "LLM"
            result = search_arxiv_papers_tool.invoke({"query": query, "max_results": 5})
            print(result)
        else:
            arxiv_id = sys.argv[1]
            result = get_arxiv_paper_tool.invoke({"arxiv_id": arxiv_id})
            print(result)
    else:
        success = run_all_tests()
        sys.exit(0 if success else 1)
