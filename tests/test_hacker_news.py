"""Unit tests for Hacker News native API tools.

Tests mock the internal helpers (_fetch_story_ids, _fetch_items_batch, _fetch_item)
to avoid network calls while exercising the tool logic and formatting.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.tools import hacker_news as hn
from src.tools.hacker_news import (
    HNToolError,
    _fetch_item,
    _fetch_story_ids,
    get_hn_top_stories,
    get_hn_best_stories,
    get_hn_new_stories,
    get_hn_ask_stories,
    get_hn_show_stories,
    get_hn_job_stories,
    get_hn_item,
    get_hn_comments,
    get_hn_user,
    get_hn_max_item_id,
    get_hn_updates,
    hn_tools,
)

# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------

MOCK_STORY = {
    "id": 12345,
    "type": "story",
    "by": "testuser",
    "time": 1234567890,
    "title": "Test Story Title",
    "url": "https://example.com",
    "score": 100,
    "descendants": 50,
}

MOCK_JOB = {
    "id": 12346,
    "type": "job",
    "by": "ycombinator",
    "time": 1234567890,
    "title": "YC Company Is Hiring",
    "url": "https://jobs.example.com",
    "score": 1,
    "descendants": 0,
}

MOCK_COMMENT = {
    "id": 12348,
    "type": "comment",
    "by": "commenter",
    "time": 1234567890,
    "text": "This is a test comment",
    "parent": 12345,
}

MOCK_USER = {
    "id": "testuser",
    "created": 1234567890,
    "karma": 5000,
    "about": "Test user bio",
    "submitted": [1, 2, 3],
}

MOCK_UPDATES = {
    "items": [12345, 12346],
    "profiles": ["user1", "user2"],
}

# Common patch targets
_P = "src.tools.hacker_news"


# ---------------------------------------------------------------------------
# hn_tools list
# ---------------------------------------------------------------------------


class TestHnToolsList:
    def test_all_tools_present(self):
        assert len(hn_tools) == 11

    def test_tool_names(self):
        names = {t.name for t in hn_tools}
        expected = {
            "get_hn_top_stories",
            "get_hn_best_stories",
            "get_hn_new_stories",
            "get_hn_ask_stories",
            "get_hn_show_stories",
            "get_hn_job_stories",
            "get_hn_item",
            "get_hn_comments",
            "get_hn_user",
            "get_hn_max_item_id",
            "get_hn_updates",
        }
        assert names == expected


# ---------------------------------------------------------------------------
# Story fetchers (top / best / new / ask / show / job)
# ---------------------------------------------------------------------------


class TestStoryFetchers:
    """All six story-list tools share _get_stories; test each category label."""

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_top_stories(self, mock_ids, mock_batch):
        mock_ids.return_value = [1, 2, 3]
        mock_batch.return_value = [MOCK_STORY, MOCK_STORY]

        result = await get_hn_top_stories.ainvoke({"limit": 2})

        assert "Top Stories" in result
        assert "Test Story Title" in result
        assert "Score: 100" in result
        mock_ids.assert_awaited_once_with("topstories")

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_best_stories(self, mock_ids, mock_batch):
        mock_ids.return_value = [1]
        mock_batch.return_value = [MOCK_STORY]

        result = await get_hn_best_stories.ainvoke({"limit": 1})

        assert "Best Stories" in result
        mock_ids.assert_awaited_once_with("beststories")

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_new_stories(self, mock_ids, mock_batch):
        mock_ids.return_value = [1]
        mock_batch.return_value = [MOCK_STORY]

        result = await get_hn_new_stories.ainvoke({"limit": 1})

        assert "New Stories" in result
        mock_ids.assert_awaited_once_with("newstories")

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_ask_stories(self, mock_ids, mock_batch):
        mock_ids.return_value = [1]
        mock_batch.return_value = [MOCK_STORY]

        result = await get_hn_ask_stories.ainvoke({"limit": 1})

        assert "Ask HN" in result
        mock_ids.assert_awaited_once_with("askstories")

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_show_stories(self, mock_ids, mock_batch):
        mock_ids.return_value = [1]
        mock_batch.return_value = [MOCK_STORY]

        result = await get_hn_show_stories.ainvoke({"limit": 1})

        assert "Show HN" in result
        mock_ids.assert_awaited_once_with("showstories")

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_job_stories(self, mock_ids, mock_batch):
        mock_ids.return_value = [1, 2]
        mock_batch.return_value = [MOCK_JOB]

        result = await get_hn_job_stories.ainvoke({"limit": 2})

        assert "Job Stories" in result
        assert "YC Company Is Hiring" in result
        mock_ids.assert_awaited_once_with("jobstories")

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_empty_results(self, mock_ids, mock_batch):
        mock_ids.return_value = []
        mock_batch.return_value = []

        result = await get_hn_top_stories.ainvoke({"limit": 5})

        assert "No Top Stories stories found" in result

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_limit_capped_to_max(self, mock_ids, mock_batch):
        """Requesting limit=100 should cap to MAX_LIMIT (30)."""
        mock_ids.return_value = list(range(100))
        mock_batch.return_value = [MOCK_STORY] * 30

        result = await get_hn_top_stories.ainvoke({"limit": 100})

        # _fetch_items_batch should be called with capped limit
        _, kwargs = mock_batch.call_args
        # positional: (ids, limit)
        called_limit = mock_batch.call_args[0][1]
        assert called_limit == 30
        assert "(30 stories)" in result

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_story_ids", new_callable=AsyncMock)
    async def test_story_format_includes_url(self, mock_ids, mock_batch):
        mock_ids.return_value = [1]
        mock_batch.return_value = [MOCK_STORY]

        result = await get_hn_top_stories.ainvoke({"limit": 1})

        assert "https://example.com" in result
        assert "testuser" in result
        assert "Comments: 50" in result


class TestFetchHelpers:
    @pytest.mark.asyncio
    async def test_fetch_item_returns_none_for_null_payload(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = None
        mock_resp.raise_for_status = MagicMock()
        client = MagicMock()
        client.get = AsyncMock(return_value=mock_resp)

        result = await _fetch_item(client, 99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_fetch_item_raises_tool_error_on_transport_failure(self):
        client = MagicMock()
        client.get = AsyncMock(side_effect=hn.httpx.ReadTimeout("timeout"))

        with pytest.raises(HNToolError, match="fetching item 12345"):
            await _fetch_item(client, 12345)

    @pytest.mark.asyncio
    async def test_fetch_story_ids_raises_tool_error_on_transport_failure(self):
        with patch(f"{_P}.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=hn.httpx.ConnectError("proxy down")
            )

            with pytest.raises(HNToolError, match="fetching topstories"):
                await _fetch_story_ids("topstories")


# ---------------------------------------------------------------------------
# get_hn_item
# ---------------------------------------------------------------------------


class TestGetItem:
    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_item", new_callable=AsyncMock)
    async def test_story_item(self, mock_fetch):
        mock_fetch.return_value = MOCK_STORY

        result = await get_hn_item.ainvoke({"item_id": 12345})

        assert "HN Item 12345 (story)" in result
        assert "Test Story Title" in result
        assert "By: testuser" in result
        assert "Score: 100" in result

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_item", new_callable=AsyncMock)
    async def test_item_not_found(self, mock_fetch):
        mock_fetch.return_value = None

        result = await get_hn_item.ainvoke({"item_id": 99999})

        assert "99999" in result
        assert "not found" in result

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_item", new_callable=AsyncMock)
    async def test_item_with_text_and_kids(self, mock_fetch):
        item = {
            **MOCK_STORY,
            "text": "Some body text",
            "kids": [1, 2, 3],
        }
        mock_fetch.return_value = item

        result = await get_hn_item.ainvoke({"item_id": 12345})

        assert "Some body text" in result
        assert "3 replies" in result


# ---------------------------------------------------------------------------
# get_hn_comments
# ---------------------------------------------------------------------------


class TestGetComments:
    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_items_batch", new_callable=AsyncMock)
    @patch(f"{_P}._fetch_item", new_callable=AsyncMock)
    async def test_comments(self, mock_fetch, mock_batch):
        parent = {**MOCK_STORY, "kids": [12348, 12349]}
        mock_fetch.return_value = parent
        mock_batch.return_value = [MOCK_COMMENT, MOCK_COMMENT]

        result = await get_hn_comments.ainvoke({"item_id": 12345, "limit": 2})

        assert "Comments on item 12345" in result
        assert "commenter" in result
        assert "This is a test comment" in result

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_item", new_callable=AsyncMock)
    async def test_no_comments(self, mock_fetch):
        mock_fetch.return_value = {**MOCK_STORY, "kids": []}

        result = await get_hn_comments.ainvoke({"item_id": 12345})

        assert "No comments" in result

    @pytest.mark.asyncio
    @patch(f"{_P}._fetch_item", new_callable=AsyncMock)
    async def test_parent_not_found(self, mock_fetch):
        mock_fetch.return_value = None

        result = await get_hn_comments.ainvoke({"item_id": 99999})

        assert "not found" in result


# ---------------------------------------------------------------------------
# get_hn_user
# ---------------------------------------------------------------------------


class TestGetUser:
    @pytest.mark.asyncio
    async def test_user_profile(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_USER
        mock_resp.raise_for_status = MagicMock()

        with patch(f"{_P}.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_resp
            )

            result = await get_hn_user.ainvoke({"username": "testuser"})

        assert "HN User: testuser" in result
        assert "Karma: 5000" in result
        assert "Test user bio" in result
        assert "Submissions: 3" in result

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = None
        mock_resp.raise_for_status = MagicMock()

        with patch(f"{_P}.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_resp
            )

            result = await get_hn_user.ainvoke({"username": "ghost"})

        assert "not found" in result

    @pytest.mark.asyncio
    async def test_user_transport_failure_raises_tool_error(self):
        with patch(f"{_P}.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=hn.httpx.ReadTimeout("timeout")
            )

            with pytest.raises(HNToolError, match="fetching user ghost"):
                await get_hn_user.ainvoke({"username": "ghost"})


# ---------------------------------------------------------------------------
# get_hn_max_item_id
# ---------------------------------------------------------------------------


class TestGetMaxItemId:
    @pytest.mark.asyncio
    async def test_returns_id(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = 47396031
        mock_resp.raise_for_status = MagicMock()

        with patch(f"{_P}.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_resp
            )

            result = await get_hn_max_item_id.ainvoke({})

        assert "47396031" in result
        assert "max HN item ID" in result

    @pytest.mark.asyncio
    async def test_transport_failure_raises_tool_error(self):
        with patch(f"{_P}.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=hn.httpx.ReadTimeout("timeout")
            )

            with pytest.raises(HNToolError, match="fetching max item ID"):
                await get_hn_max_item_id.ainvoke({})


# ---------------------------------------------------------------------------
# get_hn_updates
# ---------------------------------------------------------------------------


class TestGetUpdates:
    @pytest.mark.asyncio
    async def test_returns_updates(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = MOCK_UPDATES
        mock_resp.raise_for_status = MagicMock()

        with patch(f"{_P}.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
                return_value=mock_resp
            )

            result = await get_hn_updates.ainvoke({})

        assert "HN Recent Updates" in result
        assert "Changed items (2)" in result
        assert "Changed profiles (2)" in result
        assert "user1" in result

    @pytest.mark.asyncio
    async def test_transport_failure_raises_tool_error(self):
        with patch(f"{_P}.httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__.return_value.get = AsyncMock(
                side_effect=hn.httpx.ReadTimeout("timeout")
            )

            with pytest.raises(HNToolError, match="fetching recent updates"):
                await get_hn_updates.ainvoke({})
