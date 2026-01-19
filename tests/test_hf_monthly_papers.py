"""
Test Hugging Face monthly papers functionality.

Run with:
    pytest tests/test_hf_monthly_papers.py -v
    
Or run directly:
    python tests/test_hf_monthly_papers.py
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.tools.hf_daily_papers import (
    fetch_huggingface_monthly_papers,
    get_huggingface_papers_tool,
    _validate_month_format,
    _get_current_month,
)


def test_validate_month_format():
    """Test month format validation."""
    # Valid formats
    assert _validate_month_format("2026-01") is True
    assert _validate_month_format("2025-12") is True
    assert _validate_month_format("2024-06") is True
    
    # Invalid formats
    try:
        _validate_month_format("2026-13")  # Invalid month
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    
    try:
        _validate_month_format("2026-1")  # Missing leading zero
        assert False, "Should raise ValueError"
    except ValueError:
        pass
    
    try:
        _validate_month_format("26-01")  # Invalid year
        assert False, "Should raise ValueError"
    except ValueError:
        pass


def test_get_current_month():
    """Test getting current month."""
    month = _get_current_month()
    assert len(month) == 7  # YYYY-MM format
    assert month[4] == "-"
    assert _validate_month_format(month) is True


def test_fetch_monthly_papers():
    """Test fetching monthly papers."""
    print("\n=== Testing fetch_huggingface_monthly_papers ===")
    
    # Test with 2026-01
    papers = fetch_huggingface_monthly_papers("2026-01", limit=5)
    
    print(f"Found {len(papers)} papers for 2026-01")
    assert isinstance(papers, list)
    
    if papers:
        paper = papers[0]
        print(f"\nFirst paper:")
        print(f"  Title: {paper['title']}")
        print(f"  ArXiv ID: {paper.get('arxiv_id')}")
        print(f"  Upvotes: {paper.get('upvotes', 0)}")
        print(f"  Comments: {paper.get('num_comments', 0)}")
        
        # Verify structure
        assert "title" in paper
        assert "arxiv_id" in paper
        assert "url" in paper
        assert "upvotes" in paper
        assert "num_comments" in paper


def test_tool_with_month():
    """Test the tool with month parameter."""
    print("\n=== Testing get_huggingface_papers_tool with month ===")
    
    result = get_huggingface_papers_tool.invoke({"month": "2026-01", "limit": 3})
    print(result)
    
    assert "Monthly Papers" in result
    assert "2026-01" in result
    assert isinstance(result, str)


def test_priority():
    """Test parameter priority: month > week > date."""
    print("\n=== Testing parameter priority ===")
    
    # When month is provided, it should take precedence
    result = get_huggingface_papers_tool.invoke({
        "target_date": "2025-01-15",
        "week": "2025-W52",
        "month": "2026-01",
        "limit": 1
    })
    
    assert "Monthly Papers" in result
    assert "2026-01" in result


if __name__ == "__main__":
    print("Running Hugging Face monthly papers tests...")
    
    test_validate_month_format()
    print("✓ Month format validation test passed")
    
    test_get_current_month()
    print("✓ Get current month test passed")
    
    test_fetch_monthly_papers()
    print("✓ Fetch monthly papers test passed")
    
    test_tool_with_month()
    print("✓ Tool with month test passed")
    
    test_priority()
    print("✓ Parameter priority test passed")
    
    print("\n✅ All tests passed!")
