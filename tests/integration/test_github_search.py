"""Tests for GitHub Search Tool."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from src.tools.github_search import (
    GitHubCommitResult,
    GitHubIssueResult,
    GitHubRepoResult,
    format_commits_as_markdown,
    format_issues_as_markdown,
    format_repos_as_markdown,
    get_github_readme,
    github_readme_tool,
    github_search_tool,
    search_github_commits,
    search_github_issues,
    search_github_repos,
)


class TestGitHubRepoResult:
    """Tests for GitHubRepoResult model."""

    def test_create_with_all_fields(self):
        result = GitHubRepoResult(
            name="langchain",
            full_name="langchain-ai/langchain",
            url="https://github.com/langchain-ai/langchain",
            description="Building applications with LLMs",
            stars=50000,
            forks=10000,
            language="Python",
            updated_at="2024-01-15T00:00:00Z",
            topics=["llm", "ai", "python"],
        )
        assert result.name == "langchain"
        assert result.stars == 50000
        assert result.topics == ["llm", "ai", "python"]

    def test_optional_fields(self):
        result = GitHubRepoResult(
            name="test",
            full_name="owner/test",
            url="https://github.com/owner/test",
            stars=0,
            forks=0,
            updated_at="2024-01-01T00:00:00Z",
        )
        assert result.description is None
        assert result.language is None
        assert result.topics == []


class TestGitHubIssueResult:
    """Tests for GitHubIssueResult model."""

    def test_create_issue(self):
        result = GitHubIssueResult(
            title="Bug report",
            url="https://github.com/owner/repo/issues/1",
            state="open",
            repo="owner/repo",
            author="testuser",
            created_at="2024-01-15T00:00:00Z",
            is_pull_request=False,
            body_preview="This is a bug...",
        )
        assert result.title == "Bug report"
        assert result.is_pull_request is False

    def test_create_pr(self):
        result = GitHubIssueResult(
            title="Feature PR",
            url="https://github.com/owner/repo/pull/2",
            state="closed",
            repo="owner/repo",
            author="contributor",
            created_at="2024-01-15T00:00:00Z",
            is_pull_request=True,
        )
        assert result.is_pull_request is True
        assert result.body_preview is None


class TestGitHubCommitResult:
    """Tests for GitHubCommitResult model."""

    def test_create_commit(self):
        result = GitHubCommitResult(
            sha="abc1234",
            message="Fix critical bug",
            url="https://github.com/owner/repo/commit/abc1234",
            repo="owner/repo",
            author="developer",
            date="2024-01-15T00:00:00Z",
        )
        assert result.sha == "abc1234"
        assert result.message == "Fix critical bug"


class TestFormatReposAsMarkdown:
    """Tests for format_repos_as_markdown."""

    def test_empty_results(self):
        assert format_repos_as_markdown([]) == "No repositories found."

    def test_single_result(self):
        results = [
            GitHubRepoResult(
                name="langchain",
                full_name="langchain-ai/langchain",
                url="https://github.com/langchain-ai/langchain",
                description="Building LLM applications",
                stars=50000,
                forks=10000,
                language="Python",
                updated_at="2024-01-15T00:00:00Z",
                topics=["llm", "ai"],
            )
        ]
        markdown = format_repos_as_markdown(results)

        assert "langchain-ai/langchain" in markdown
        assert "50,000" in markdown  # Formatted star count
        assert "Python" in markdown
        assert "llm, ai" in markdown


class TestFormatIssuesAsMarkdown:
    """Tests for format_issues_as_markdown."""

    def test_empty_results(self):
        assert format_issues_as_markdown([]) == "No issues or pull requests found."

    def test_issue_formatting(self):
        results = [
            GitHubIssueResult(
                title="Test Issue",
                url="https://github.com/owner/repo/issues/1",
                state="open",
                repo="owner/repo",
                author="testuser",
                created_at="2024-01-15T00:00:00Z",
                is_pull_request=False,
            )
        ]
        markdown = format_issues_as_markdown(results)

        assert "[Issue]" in markdown
        assert "Test Issue" in markdown
        assert "🟢" in markdown  # Open state emoji


class TestFormatCommitsAsMarkdown:
    """Tests for format_commits_as_markdown."""

    def test_empty_results(self):
        assert format_commits_as_markdown([]) == "No commits found."

    def test_commit_formatting(self):
        results = [
            GitHubCommitResult(
                sha="abc1234",
                message="Fix bug",
                url="https://github.com/owner/repo/commit/abc1234",
                repo="owner/repo",
                author="developer",
                date="2024-01-15T00:00:00Z",
            )
        ]
        markdown = format_commits_as_markdown(results)

        assert "`abc1234`" in markdown
        assert "Fix bug" in markdown


class TestSearchGitHubRepos:
    """Tests for search_github_repos function."""

    @patch("src.tools.github_search.requests.get")
    def test_search_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [
                    {
                        "name": "langchain",
                        "full_name": "langchain-ai/langchain",
                        "html_url": "https://github.com/langchain-ai/langchain",
                        "description": "LLM framework",
                        "stargazers_count": 50000,
                        "forks_count": 10000,
                        "language": "Python",
                        "updated_at": "2024-01-15T00:00:00Z",
                        "topics": ["llm"],
                    }
                ]
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()

        results = search_github_repos("langchain")

        assert len(results) == 1
        assert results[0].name == "langchain"
        assert results[0].stars == 50000

    @patch("src.tools.github_search.requests.get")
    def test_rate_limit_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": "1234567890",
        }
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="rate limit exceeded"):
            search_github_repos("test")


class TestSearchGitHubIssues:
    """Tests for search_github_issues function."""

    @patch("src.tools.github_search.requests.get")
    def test_search_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [
                    {
                        "title": "Bug report",
                        "html_url": "https://github.com/owner/repo/issues/1",
                        "state": "open",
                        "repository_url": "https://api.github.com/repos/owner/repo",
                        "user": {"login": "testuser"},
                        "created_at": "2024-01-15T00:00:00Z",
                        "body": "Description here",
                    }
                ]
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()

        results = search_github_issues("bug")

        assert len(results) == 1
        assert results[0].title == "Bug report"
        assert results[0].repo == "owner/repo"
        assert results[0].is_pull_request is False


class TestSearchGitHubCommits:
    """Tests for search_github_commits function."""

    @patch("src.tools.github_search.requests.get")
    def test_search_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            json=lambda: {
                "items": [
                    {
                        "sha": "abc1234567890",
                        "html_url": "https://github.com/owner/repo/commit/abc1234",
                        "commit": {
                            "message": "Fix bug\n\nDetailed description",
                            "author": {"name": "developer"},
                            "committer": {"date": "2024-01-15T00:00:00Z"},
                        },
                        "repository": {"full_name": "owner/repo"},
                    }
                ]
            },
        )
        mock_get.return_value.raise_for_status = MagicMock()

        results = search_github_commits("fix bug")

        assert len(results) == 1
        assert results[0].sha == "abc1234"  # Shortened SHA
        assert results[0].message == "Fix bug"  # First line only
        assert results[0].repo == "owner/repo"


class TestGitHubSearchTool:
    """Tests for the LangChain tool wrapper."""

    @patch("src.tools.github_search.search_github_repos")
    def test_repo_search(self, mock_search):
        mock_search.return_value = [
            GitHubRepoResult(
                name="test",
                full_name="owner/test",
                url="https://github.com/owner/test",
                stars=100,
                forks=10,
                updated_at="2024-01-01T00:00:00Z",
            )
        ]

        result = github_search_tool.invoke({"query": "test"})

        assert "owner/test" in result
        mock_search.assert_called_with("test", count=5)

    @patch("src.tools.github_search.search_github_issues")
    def test_issue_search(self, mock_search):
        mock_search.return_value = []

        result = github_search_tool.invoke(
            {"query": "bug", "search_type": "issues", "count": 10}
        )

        assert "No issues" in result
        mock_search.assert_called_with("bug", count=10)

    @patch("src.tools.github_search.search_github_commits")
    def test_commit_search(self, mock_search):
        mock_search.return_value = []

        result = github_search_tool.invoke(
            {"query": "fix", "search_type": "commits"}
        )

        assert "No commits" in result

    @patch("src.tools.github_search.search_github_repos")
    def test_count_clamped(self, mock_search):
        mock_search.return_value = []

        # Count should be clamped to 20
        github_search_tool.invoke({"query": "test", "count": 50})
        mock_search.assert_called_with("test", count=20)

        # Count should be clamped to 1
        github_search_tool.invoke({"query": "test", "count": 0})
        mock_search.assert_called_with("test", count=1)

    @patch("src.tools.github_search.search_github_repos")
    def test_error_handling(self, mock_search):
        mock_search.side_effect = ValueError("rate limit exceeded")

        result = github_search_tool.invoke({"query": "test"})

        assert "Error" in result
        assert "rate limit" in result


class TestGetGitHubReadme:
    """Tests for get_github_readme function."""

    @patch("src.tools.github_search.requests.get")
    def test_get_readme_success(self, mock_get):
        mock_get.return_value = MagicMock(
            status_code=200,
            text="# My Project\n\nThis is the README content.",
        )
        mock_get.return_value.raise_for_status = MagicMock()

        content = get_github_readme("owner/repo")

        assert "My Project" in content
        assert "README content" in content

    def test_invalid_repo_format(self):
        with pytest.raises(ValueError, match="Invalid repository format"):
            get_github_readme("invalid-repo")

        with pytest.raises(ValueError, match="Invalid repository format"):
            get_github_readme("too/many/slashes")

    @patch("src.tools.github_search.requests.get")
    def test_rate_limit_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 403
        mock_response.headers = {"X-RateLimit-Remaining": "0"}
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="rate limit exceeded"):
            get_github_readme("owner/repo")

    @patch("src.tools.github_search.requests.get")
    def test_not_found_error(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        with pytest.raises(ValueError, match="not found"):
            get_github_readme("owner/nonexistent")


class TestGitHubReadmeTool:
    """Tests for the github_readme_tool LangChain tool."""

    @patch("src.tools.github_search.get_github_readme")
    def test_success(self, mock_get_readme):
        mock_get_readme.return_value = "# Test README\n\nContent here."

        result = github_readme_tool.invoke({"repo": "owner/repo"})

        assert "README: owner/repo" in result
        assert "Test README" in result
        assert "https://github.com/owner/repo" in result

    @patch("src.tools.github_search.get_github_readme")
    def test_error_handling(self, mock_get_readme):
        mock_get_readme.side_effect = ValueError("rate limit exceeded")

        result = github_readme_tool.invoke({"repo": "owner/repo"})

        assert "Error" in result
        assert "rate limit" in result

    @patch("src.tools.github_search.get_github_readme")
    def test_not_found(self, mock_get_readme):
        mock_get_readme.side_effect = ValueError("Repository 'owner/repo' or its README not found.")

        result = github_readme_tool.invoke({"repo": "owner/repo"})

        assert "Error" in result
        assert "not found" in result

