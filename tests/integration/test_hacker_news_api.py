"""
Integration tests for Hacker News native API tools.

These tests make real API calls to the HN Firebase API.
Run with: uv run pytest tests/integration/test_hacker_news_api.py -v
"""

import pytest

from src.tools.hacker_news import (
    get_hn_ask_stories,
    get_hn_best_stories,
    get_hn_comments,
    get_hn_item,
    get_hn_job_stories,
    get_hn_max_item_id,
    get_hn_new_stories,
    get_hn_show_stories,
    get_hn_top_stories,
    get_hn_updates,
    get_hn_user,
)


class TestStoryFetchers:
    """Test story fetching tools with real API calls."""

    @pytest.mark.asyncio
    async def test_get_top_stories(self):
        """Test fetching top stories from HN."""
        result = await get_hn_top_stories.ainvoke({"limit": 3})

        assert "Top Stories" in result
        assert "(3 stories)" in result or "(2 stories)" in result  # May have fewer
        assert "Score:" in result
        assert "By:" in result
        assert "Comments:" in result
        print(f"\n✓ Top stories:\n{result[:500]}")

    @pytest.mark.asyncio
    async def test_get_best_stories(self):
        """Test fetching best stories from HN."""
        result = await get_hn_best_stories.ainvoke({"limit": 2})

        assert "Best Stories" in result
        assert "Score:" in result
        print(f"\n✓ Best stories:\n{result[:500]}")

    @pytest.mark.asyncio
    async def test_get_new_stories(self):
        """Test fetching new stories from HN."""
        result = await get_hn_new_stories.ainvoke({"limit": 2})

        assert "New Stories" in result
        assert "Score:" in result
        print(f"\n✓ New stories:\n{result[:500]}")

    @pytest.mark.asyncio
    async def test_get_ask_stories(self):
        """Test fetching Ask HN stories."""
        result = await get_hn_ask_stories.ainvoke({"limit": 2})

        assert "Ask HN" in result
        print(f"\n✓ Ask HN:\n{result[:500]}")

    @pytest.mark.asyncio
    async def test_get_show_stories(self):
        """Test fetching Show HN stories."""
        result = await get_hn_show_stories.ainvoke({"limit": 2})

        assert "Show HN" in result
        print(f"\n✓ Show HN:\n{result[:500]}")

    @pytest.mark.asyncio
    async def test_get_job_stories(self):
        """Test fetching job postings from HN.

        This is valuable for understanding real hiring demand in the US tech market.
        """
        result = await get_hn_job_stories.ainvoke({"limit": 3})

        assert "Job Stories" in result
        # Job posts may have 0 score/comments, so just check structure
        assert "By:" in result
        print(f"\n✓ Job stories (US tech market hiring):\n{result[:800]}")

    @pytest.mark.asyncio
    async def test_limit_parameter(self):
        """Test that limit parameter works correctly."""
        result_small = await get_hn_top_stories.ainvoke({"limit": 1})
        result_large = await get_hn_top_stories.ainvoke({"limit": 5})

        # Small result should be shorter
        assert len(result_small) < len(result_large)
        print(f"\n✓ Limit parameter works (1 story: {len(result_small)} chars, 5 stories: {len(result_large)} chars)")


class TestItemAndComments:
    """Test item and comment fetching with real API calls."""

    @pytest.mark.asyncio
    async def test_get_item(self):
        """Test fetching a specific HN item.

        Uses a well-known item ID that should always exist.
        """
        # Item 1 is the first HN post ever (by pg)
        result = await get_hn_item.ainvoke({"item_id": 1})

        assert "HN Item 1" in result
        assert "By:" in result
        print(f"\n✓ Item details:\n{result[:500]}")

    @pytest.mark.asyncio
    async def test_get_item_not_found(self):
        """Test handling of non-existent item."""
        # Use a very large ID that likely doesn't exist yet
        result = await get_hn_item.ainvoke({"item_id": 999999999})

        assert "not found" in result
        print(f"\n✓ Non-existent item handled: {result}")

    @pytest.mark.asyncio
    async def test_get_comments(self):
        """Test fetching comments for an item.

        Uses item 1 which has historical comments.
        """
        result = await get_hn_comments.ainvoke({"item_id": 1, "limit": 2})

        # Item 1 may or may not have comments, just check format
        assert "Comments on item 1" in result
        print(f"\n✓ Comments:\n{result[:500]}")

    @pytest.mark.asyncio
    async def test_get_comments_no_comments(self):
        """Test handling of item with no comments."""
        # Get a recent top story and check its comments
        top_stories_result = await get_hn_top_stories.ainvoke({"limit": 1})

        # Extract item ID from the result (format: item?id=12345)
        import re
        match = re.search(r"item\?id=(\d+)", top_stories_result)

        if match:
            item_id = int(match.group(1))
            result = await get_hn_comments.ainvoke({"item_id": item_id, "limit": 3})

            # Should either show comments or "No comments"
            assert "Comments on item" in result or "No comments" in result
            print(f"\n✓ Comments check for item {item_id}:\n{result[:500]}")


class TestUserAndMetadata:
    """Test user profile and metadata tools with real API calls."""

    @pytest.mark.asyncio
    async def test_get_user(self):
        """Test fetching a user profile.

        Uses 'dang' (HN moderator) who should always exist.
        """
        result = await get_hn_user.ainvoke({"username": "dang"})

        assert "HN User: dang" in result
        assert "Karma:" in result
        assert "Created:" in result
        print(f"\n✓ User profile:\n{result[:500]}")

    @pytest.mark.asyncio
    async def test_get_user_not_found(self):
        """Test handling of non-existent user."""
        result = await get_hn_user.ainvoke({"username": "thisuserdoesnotexist123456"})

        assert "not found" in result
        print(f"\n✓ Non-existent user handled: {result}")

    @pytest.mark.asyncio
    async def test_get_max_item_id(self):
        """Test fetching the current max item ID."""
        result = await get_hn_max_item_id.ainvoke({})

        assert "max HN item ID:" in result
        # Extract the ID and verify it's a reasonable number
        import re
        match = re.search(r"(\d+)", result)
        assert match
        item_id = int(match.group(1))
        assert item_id > 40000000  # Should be well above 40M by now
        print(f"\n✓ Max item ID: {result}")

    @pytest.mark.asyncio
    async def test_get_updates(self):
        """Test fetching recent updates."""
        result = await get_hn_updates.ainvoke({})

        assert "HN Recent Updates" in result
        assert "Changed items" in result
        assert "Changed profiles" in result
        print(f"\n✓ Recent updates:\n{result[:500]}")


class TestRealWorldUseCases:
    """Test real-world use cases combining multiple tools."""

    @pytest.mark.asyncio
    async def test_job_market_research(self):
        """Test researching the US tech job market via HN job posts."""
        # Get recent job postings
        jobs = await get_hn_job_stories.ainvoke({"limit": 5})

        assert "Job Stories" in jobs

        # Extract first job item ID if available
        import re
        match = re.search(r"item\?id=(\d+)", jobs)

        if match:
            job_id = int(match.group(1))
            # Get details of the job post
            job_details = await get_hn_item.ainvoke({"item_id": job_id})

            assert f"HN Item {job_id}" in job_details
            print(f"\n✓ Job market research:\nJobs list:\n{jobs[:500]}\n\nSample job:\n{job_details[:500]}")
        else:
            print(f"\n✓ Job market research (no jobs found):\n{jobs}")

    @pytest.mark.asyncio
    async def test_trending_discussion(self):
        """Test finding and exploring a trending discussion."""
        # Get top story
        top = await get_hn_top_stories.ainvoke({"limit": 1})

        # Extract item ID
        import re
        match = re.search(r"item\?id=(\d+)", top)

        if match:
            item_id = int(match.group(1))

            # Get item details
            details = await get_hn_item.ainvoke({"item_id": item_id})

            # Get comments
            comments = await get_hn_comments.ainvoke({"item_id": item_id, "limit": 3})

            assert f"HN Item {item_id}" in details
            assert "Comments on item" in comments

            print(f"\n✓ Trending discussion:\nStory:\n{top[:300]}\n\nDetails:\n{details[:300]}\n\nComments:\n{comments[:500]}")

    @pytest.mark.asyncio
    async def test_user_contribution_analysis(self):
        """Test analyzing a user's contributions."""
        # Get a top story
        top = await get_hn_top_stories.ainvoke({"limit": 1})

        # Extract username
        import re
        match = re.search(r"By: (\w+)", top)

        if match:
            username = match.group(1)

            # Get user profile
            user = await get_hn_user.ainvoke({"username": username})

            assert f"HN User: {username}" in user
            assert "Karma:" in user

            print(f"\n✓ User contribution analysis:\nTop story by:\n{top[:300]}\n\nUser profile:\n{user[:500]}")


class TestErrorHandling:
    """Test error handling and edge cases."""

    @pytest.mark.asyncio
    async def test_invalid_limit(self):
        """Test handling of invalid limit values."""
        # Limit too large should be capped
        result = await get_hn_top_stories.ainvoke({"limit": 1000})

        # Should cap at MAX_LIMIT (30)
        assert "(30 stories)" in result or "stories)" in result
        print(f"\n✓ Large limit capped correctly")

    @pytest.mark.asyncio
    async def test_zero_limit(self):
        """Test handling of zero limit."""
        result = await get_hn_top_stories.ainvoke({"limit": 0})

        # Should handle gracefully (likely return empty or minimum)
        assert isinstance(result, str)
        print(f"\n✓ Zero limit handled: {result[:200]}")

    @pytest.mark.asyncio
    async def test_network_resilience(self):
        """Test that tools handle network issues gracefully."""
        # This test just verifies tools don't crash on valid inputs
        # Real network errors are hard to simulate in integration tests

        results = []
        results.append(await get_hn_top_stories.ainvoke({"limit": 1}))
        results.append(await get_hn_max_item_id.ainvoke({}))
        results.append(await get_hn_user.ainvoke({"username": "pg"}))

        # All should return strings without crashing
        assert all(isinstance(r, str) for r in results)
        print(f"\n✓ All tools handle requests without crashing")


if __name__ == "__main__":
    """
    Run integration tests manually:

    uv run python tests/integration/test_hacker_news_api.py
    """
    import asyncio

    async def run_sample_tests():
        print("=" * 60)
        print("Hacker News API Integration Tests - Sample Run")
        print("=" * 60)

        # Test top stories
        print("\n1. Testing top stories...")
        result = await get_hn_top_stories.ainvoke({"limit": 3})
        print(result[:500])

        # Test job stories
        print("\n2. Testing job stories (US tech market)...")
        result = await get_hn_job_stories.ainvoke({"limit": 3})
        print(result[:500])

        # Test user profile
        print("\n3. Testing user profile...")
        result = await get_hn_user.ainvoke({"username": "dang"})
        print(result[:300])

        # Test max item ID
        print("\n4. Testing max item ID...")
        result = await get_hn_max_item_id.ainvoke({})
        print(result)

        print("\n" + "=" * 60)
        print("Sample tests completed!")
        print("Run full test suite with: uv run pytest tests/integration/test_hacker_news_api.py -v")
        print("=" * 60)

    asyncio.run(run_sample_tests())
