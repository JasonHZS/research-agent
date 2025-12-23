"""
GitHub Search Tool

This module provides functionality to search GitHub repositories, issues,
and commits using the GitHub REST API without authentication.

API Documentation: https://docs.github.com/en/rest/search

Note: Unauthenticated requests are limited to 10 requests per minute.
"""

from typing import Literal, Optional

import requests
from langchain_core.tools import tool
from pydantic import BaseModel, Field


# GitHub API base URL
GITHUB_API_BASE = "https://api.github.com"

# Common headers for GitHub API
GITHUB_HEADERS = {
    "Accept": "application/vnd.github+json",
    "X-GitHub-Api-Version": "2022-11-28",
}


class GitHubRepoResult(BaseModel):
    """A GitHub repository search result."""

    name: str
    full_name: str
    url: str
    description: Optional[str] = None
    stars: int
    forks: int
    language: Optional[str] = None
    updated_at: str
    topics: list[str] = Field(default_factory=list)


class GitHubIssueResult(BaseModel):
    """A GitHub issue or pull request search result."""

    title: str
    url: str
    state: str
    repo: str
    author: str
    created_at: str
    is_pull_request: bool
    body_preview: Optional[str] = None


class GitHubCommitResult(BaseModel):
    """A GitHub commit search result."""

    sha: str
    message: str
    url: str
    repo: str
    author: str
    date: str


def _make_github_request(endpoint: str, params: dict) -> dict:
    """
    Make a request to the GitHub API.

    Args:
        endpoint: API endpoint path (e.g., '/search/repositories').
        params: Query parameters.

    Returns:
        JSON response as a dictionary.

    Raises:
        requests.RequestException: If the request fails.
        ValueError: If the API returns an error.
    """
    url = f"{GITHUB_API_BASE}{endpoint}"
    response = requests.get(url, headers=GITHUB_HEADERS, params=params, timeout=30)

    # Handle rate limiting
    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining")
        reset_time = response.headers.get("X-RateLimit-Reset", "unknown")
        message = ""

        try:
            message = response.json().get("message") or ""
        except ValueError:
            message = response.text or ""

        normalized_message = message.lower()
        if (remaining is not None and remaining == "0") or "rate limit" in normalized_message:
            raise ValueError(
                f"GitHub API rate limit exceeded. Remaining: {remaining or '0'}, "
                f"Reset time: {reset_time}"
            )

        raise ValueError(
            f"GitHub API returned 403 Forbidden: {message or 'Access denied or abuse detection triggered.'}"
        )

    response.raise_for_status()
    return response.json()


def search_github_repos(
    query: str,
    count: int = 5,
    sort: str = "stars",
    order: str = "desc",
) -> list[GitHubRepoResult]:
    """
    Search GitHub repositories.

    Args:
        query: Search query string. Supports GitHub search syntax
               (e.g., 'machine learning language:python stars:>1000').
        count: Number of results to return (1-100, default: 5).
        sort: Sort field ('stars', 'forks', 'help-wanted-issues', 'updated').
        order: Sort order ('asc' or 'desc').

    Returns:
        A list of GitHubRepoResult objects.
    """
    params = {
        "q": query,
        "per_page": min(count, 100),
        "sort": sort,
        "order": order,
    }

    data = _make_github_request("/search/repositories", params)
    items = data.get("items", [])

    results = []
    for item in items:
        results.append(
            GitHubRepoResult(
                name=item.get("name", ""),
                full_name=item.get("full_name", ""),
                url=item.get("html_url", ""),
                description=item.get("description"),
                stars=item.get("stargazers_count", 0),
                forks=item.get("forks_count", 0),
                language=item.get("language"),
                updated_at=item.get("updated_at", ""),
                topics=item.get("topics", []),
            )
        )

    return results


def search_github_issues(
    query: str,
    count: int = 5,
    sort: str = "created",
    order: str = "desc",
) -> list[GitHubIssueResult]:
    """
    Search GitHub issues and pull requests.

    Args:
        query: Search query string. Supports GitHub search syntax
               (e.g., 'bug label:help-wanted state:open').
        count: Number of results to return (1-100, default: 5).
        sort: Sort field ('comments', 'reactions', 'created', 'updated').
        order: Sort order ('asc' or 'desc').

    Returns:
        A list of GitHubIssueResult objects.
    """
    params = {
        "q": query,
        "per_page": min(count, 100),
        "sort": sort,
        "order": order,
    }

    data = _make_github_request("/search/issues", params)
    items = data.get("items", [])

    results = []
    for item in items:
        # Extract repo name from repository_url
        repo_url = item.get("repository_url", "")
        repo = repo_url.split("/repos/")[-1] if "/repos/" in repo_url else ""

        # Truncate body for preview
        body = item.get("body") or ""
        body_preview = body[:200] + "..." if len(body) > 200 else body if body else None

        results.append(
            GitHubIssueResult(
                title=item.get("title", ""),
                url=item.get("html_url", ""),
                state=item.get("state", ""),
                repo=repo,
                author=item.get("user", {}).get("login", "unknown"),
                created_at=item.get("created_at", ""),
                is_pull_request="pull_request" in item,
                body_preview=body_preview,
            )
        )

    return results


def search_github_commits(
    query: str,
    count: int = 5,
    sort: str = "committer-date",
    order: str = "desc",
) -> list[GitHubCommitResult]:
    """
    Search GitHub commits.

    Args:
        query: Search query string. Supports GitHub search syntax
               (e.g., 'fix bug repo:owner/repo').
        count: Number of results to return (1-100, default: 5).
        sort: Sort field ('committer-date' or 'author-date').
        order: Sort order ('asc' or 'desc').

    Returns:
        A list of GitHubCommitResult objects.
    """
    # Commits search requires special preview header
    headers = {
        **GITHUB_HEADERS,
        "Accept": "application/vnd.github.cloak-preview+json",
    }

    params = {
        "q": query,
        "per_page": min(count, 100),
        "sort": sort,
        "order": order,
    }

    url = f"{GITHUB_API_BASE}/search/commits"
    response = requests.get(url, headers=headers, params=params, timeout=30)

    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
        raise ValueError(f"GitHub API rate limit exceeded. Remaining: {remaining}")

    response.raise_for_status()
    data = response.json()
    items = data.get("items", [])

    results = []
    for item in items:
        commit = item.get("commit", {})
        repo = item.get("repository", {}).get("full_name", "")

        # Get commit message (first line only)
        message = commit.get("message", "")
        message = message.split("\n")[0] if message else ""

        results.append(
            GitHubCommitResult(
                sha=item.get("sha", "")[:7],  # Short SHA
                message=message,
                url=item.get("html_url", ""),
                repo=repo,
                author=commit.get("author", {}).get("name", "unknown"),
                date=commit.get("committer", {}).get("date", ""),
            )
        )

    return results


def format_repos_as_markdown(results: list[GitHubRepoResult]) -> str:
    """Format repository results as markdown."""
    if not results:
        return "No repositories found."

    parts = [f"# GitHub Repositories ({len(results)} results)\n"]

    for i, repo in enumerate(results, 1):
        result_parts = [f"## {i}. [{repo.full_name}]({repo.url})"]

        if repo.description:
            result_parts.append(f"\n{repo.description}")

        # Stats line
        stats = [f"⭐ {repo.stars:,}"]
        if repo.forks:
            stats.append(f"🔀 {repo.forks:,}")
        if repo.language:
            stats.append(f"📝 {repo.language}")
        result_parts.append(f"\n**Stats:** {' | '.join(stats)}")

        # Topics
        if repo.topics:
            result_parts.append(f"**Topics:** {', '.join(repo.topics[:5])}")

        # Updated date
        if repo.updated_at:
            date_str = repo.updated_at.split("T")[0]
            result_parts.append(f"**Updated:** {date_str}")

        parts.append("\n".join(result_parts))

    return "\n\n---\n\n".join(parts)


def format_issues_as_markdown(results: list[GitHubIssueResult]) -> str:
    """Format issue/PR results as markdown."""
    if not results:
        return "No issues or pull requests found."

    parts = [f"# GitHub Issues/PRs ({len(results)} results)\n"]

    for i, issue in enumerate(results, 1):
        type_label = "PR" if issue.is_pull_request else "Issue"
        state_emoji = "🟢" if issue.state == "open" else "🔴"

        result_parts = [f"## {i}. [{type_label}] {issue.title}"]
        result_parts.append(f"**URL:** {issue.url}")
        result_parts.append(f"**Repo:** {issue.repo}")
        result_parts.append(f"**State:** {state_emoji} {issue.state}")
        result_parts.append(f"**Author:** {issue.author}")

        if issue.created_at:
            date_str = issue.created_at.split("T")[0]
            result_parts.append(f"**Created:** {date_str}")

        if issue.body_preview:
            result_parts.append(f"\n> {issue.body_preview}")

        parts.append("\n".join(result_parts))

    return "\n\n---\n\n".join(parts)


def format_commits_as_markdown(results: list[GitHubCommitResult]) -> str:
    """Format commit results as markdown."""
    if not results:
        return "No commits found."

    parts = [f"# GitHub Commits ({len(results)} results)\n"]

    for i, commit in enumerate(results, 1):
        result_parts = [f"## {i}. `{commit.sha}` - {commit.message}"]
        result_parts.append(f"**URL:** {commit.url}")
        result_parts.append(f"**Repo:** {commit.repo}")
        result_parts.append(f"**Author:** {commit.author}")

        if commit.date:
            date_str = commit.date.split("T")[0]
            result_parts.append(f"**Date:** {date_str}")

        parts.append("\n".join(result_parts))

    return "\n\n---\n\n".join(parts)


def get_github_readme(repo: str) -> str:
    """
    Get the README content of a GitHub repository.

    Args:
        repo: Repository full name in 'owner/repo' format (e.g., 'langchain-ai/langchain').

    Returns:
        The README content as markdown text.

    Raises:
        ValueError: If the repository or README is not found, or rate limit exceeded.
        requests.RequestException: If the request fails.
    """
    # Validate repo format
    if "/" not in repo or repo.count("/") != 1:
        raise ValueError(
            f"Invalid repository format '{repo}'. Use 'owner/repo' format."
        )

    url = f"{GITHUB_API_BASE}/repos/{repo}/readme"
    # Request raw content directly
    headers = {
        **GITHUB_HEADERS,
        "Accept": "application/vnd.github.raw+json",
    }

    response = requests.get(url, headers=headers, timeout=30)

    # Handle errors
    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining", "unknown")
        raise ValueError(f"GitHub API rate limit exceeded. Remaining: {remaining}")
    elif response.status_code == 404:
        raise ValueError(f"Repository '{repo}' or its README not found.")

    response.raise_for_status()

    # Return the raw README content
    return response.text


def _handle_request_error(e: requests.RequestException, query: str) -> str:
    """Handle request exceptions and return user-friendly error messages."""
    if hasattr(e, "response") and e.response is not None:
        status_code = e.response.status_code
        if status_code == 403:
            return (
                "Error: GitHub API rate limit exceeded. "
                "Unauthenticated requests are limited to 10 per minute."
            )
        elif status_code == 422:
            return f"Error: Invalid search query '{query}'. Please check the syntax."
        return f"Error searching GitHub for '{query}': HTTP {status_code}"
    return f"Error searching GitHub for '{query}': Network error - {str(e)}"


SearchType = Literal["repositories", "issues", "commits"]


@tool
def github_search_tool(
    query: str,
    search_type: SearchType = "repositories",
    count: int = 5,
) -> str:
    """
    Search GitHub for repositories, issues/PRs, or commits (NO AUTH REQUIRED).

    RATE LIMIT: Only 10 requests per minute without authentication.
    Use sparingly and prefer other tools when possible.

    Search Types:
    - repositories: Find open-source projects by name, description, topics
    - issues: Find discussions, bug reports, feature requests, and PRs
    - commits: Find specific code changes by message or author

    Query Syntax Examples:
    - Repos: "machine learning language:python stars:>1000"
    - Issues: "bug label:help-wanted state:open"
    - Commits: "fix security repo:owner/repo"

    Args:
        query: Search query string. Supports GitHub search qualifiers.
        search_type: Type of search - 'repositories', 'issues', or 'commits'.
        count: Number of results to return (1-20, default: 5).

    Returns:
        Markdown-formatted list of search results.
    """
    # Clamp count to reasonable range for unauthenticated use
    count = max(1, min(count, 20))

    try:
        if search_type == "repositories":
            results = search_github_repos(query, count=count)
            return format_repos_as_markdown(results)
        elif search_type == "issues":
            results = search_github_issues(query, count=count)
            return format_issues_as_markdown(results)
        elif search_type == "commits":
            results = search_github_commits(query, count=count)
            return format_commits_as_markdown(results)
        else:
            return f"Error: Unknown search type '{search_type}'. Use 'repositories', 'issues', or 'commits'."

    except ValueError as e:
        return f"Error: {str(e)}"
    except requests.RequestException as e:
        return _handle_request_error(e, query)
    except Exception as e:
        return f"Error searching GitHub: Unexpected error - {str(e)}"


@tool
def github_readme_tool(repo: str) -> str:
    """
    Get the README content of a GitHub repository (NO AUTH REQUIRED).

    Use this tool to read the full README documentation of a specific repository
    after finding it via github_search_tool.

    RATE LIMIT: Only 10 requests per minute without authentication.
    Use sparingly - only fetch README for repositories you're genuinely interested in.

    Args:
        repo: Repository full name in 'owner/repo' format.
              Example: 'langchain-ai/langchain', 'microsoft/markitdown'

    Returns:
        The README content as markdown text, or an error message.
    """
    try:
        content = get_github_readme(repo)

        # Add header with repo info
        header = f"# README: {repo}\n\n**Source:** https://github.com/{repo}\n\n---\n\n"
        return header + content

    except ValueError as e:
        return f"Error: {str(e)}"
    except requests.RequestException as e:
        if hasattr(e, "response") and e.response is not None:
            status_code = e.response.status_code
            if status_code == 403:
                return (
                    "Error: GitHub API rate limit exceeded. "
                    "Unauthenticated requests are limited to 10 per minute."
                )
            return f"Error fetching README for '{repo}': HTTP {status_code}"
        return f"Error fetching README for '{repo}': Network error - {str(e)}"
    except Exception as e:
        return f"Error fetching README: Unexpected error - {str(e)}"


# For direct testing
if __name__ == "__main__":
    print("=== Testing GitHub Search Tool ===\n")

    # Test repository search
    # print("1. Repository Search: 'langchain'")
    # result = github_search_tool.invoke({"query": "langchain", "count": 3})
    # print(result)
    # print("\n" + "=" * 50 + "\n")

    # # Test issue search
    # print("2. Issue Search: 'bug state:open'")
    # result = github_search_tool.invoke(
    #     {"query": "bug state:open repo:langchain-ai/langchain", "search_type": "issues", "count": 3}
    # )
    # print(result)
    # print("\n" + "=" * 50 + "\n")

    # Test README fetch
    print("3. README Fetch: 'slopus/happy'")
    result = github_readme_tool.invoke({"repo": "slopus/happy"})
    print(result)
