"""Tests for Bocha Web Search Tool."""

import os
from unittest.mock import MagicMock, patch

import pytest

from src.tools.bocha_search import (
    SearchResult,
    bocha_web_search_tool,
    format_search_results_as_markdown,
    search_web,
)


class TestSearchResult:
    """Tests for SearchResult model."""

    def test_create_with_all_fields(self):
        result = SearchResult(
            name="Test",
            url="https://example.com",
            summary="Summary",
            date_published="2024-07-22T00:00:00Z",
        )
        assert result.name == "Test"
        assert result.date_published == "2024-07-22T00:00:00Z"

    def test_date_published_optional(self):
        result = SearchResult(name="Test", url="https://example.com", summary="Summary")
        assert result.date_published is None


class TestFormatSearchResults:
    """Tests for format_search_results_as_markdown."""

    def test_empty_results(self):
        assert format_search_results_as_markdown([]) == "No search results found."

    def test_single_result_with_date(self):
        results = [
            SearchResult(
                name="Test Article",
                url="https://example.com",
                summary="Test summary",
                date_published="2024-07-22T00:00:00Z",
            )
        ]
        markdown = format_search_results_as_markdown(results)

        assert "## 1. Test Article" in markdown
        assert "**URL:** https://example.com" in markdown
        assert "**Date:** 2024-07-22" in markdown


class TestSearchWeb:
    """Tests for search_web function."""

    def test_missing_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError, match="BOCHA_API_KEY is required"):
                search_web("test query")

    @patch("src.tools.bocha_search.requests.post")
    def test_search_success(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {
                "code": 200,
                "data": {
                    "webPages": {
                        "value": [
                            {
                                "name": "Test",
                                "displayUrl": "https://example.com",
                                "summary": "Summary",
                                "datePublished": "2024-07-22T00:00:00Z",
                            }
                        ]
                    }
                },
            }
        )

        results = search_web("test", api_key="test-key")

        assert len(results) == 1
        assert results[0].name == "Test"
        assert results[0].url == "https://example.com"

    @patch("src.tools.bocha_search.requests.post")
    def test_api_error(self, mock_post):
        mock_post.return_value = MagicMock(
            json=lambda: {"code": 400, "msg": "Invalid request"}
        )

        with pytest.raises(ValueError, match="Bocha API error"):
            search_web("test", api_key="test-key")


class TestBochaWebSearchTool:
    """Tests for the LangChain tool wrapper."""

    @patch("src.tools.bocha_search.search_web")
    def test_success(self, mock_search):
        mock_search.return_value = [
            SearchResult(name="Test", url="https://example.com", summary="Summary")
        ]
        result = bocha_web_search_tool.invoke({"query": "test"})
        assert "Test" in result

    @patch("src.tools.bocha_search.search_web")
    def test_count_clamped(self, mock_search):
        mock_search.return_value = []

        bocha_web_search_tool.invoke({"query": "test", "count": 50})
        mock_search.assert_called_with("test", count=20)

        bocha_web_search_tool.invoke({"query": "test", "count": 0})
        mock_search.assert_called_with("test", count=1)
