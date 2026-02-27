"""Tests for RSS feeds tool."""

import concurrent.futures
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.tools.rss_feeds import (
    FeedInfo,
    _fetch_single_feed,
    _match_feed,
    _parse_opml,
    fetch_rss_articles_tool,
    get_feeds_latest_overview_tool,
    list_rss_feeds_tool,
)


# Reset cache before each test
@pytest.fixture(autouse=True)
def _reset_cache(monkeypatch: pytest.MonkeyPatch):
    import src.tools.rss_feeds as mod

    mod._feeds_cache = {}
    mock_response = MagicMock()
    mock_response.content = b"<rss></rss>"
    mock_response.raise_for_status.return_value = None
    monkeypatch.setattr(mod.requests, "get", MagicMock(return_value=mock_response))
    yield
    mod._feeds_cache = {}


SAMPLE_OPML = """\
<?xml version="1.0" encoding="UTF-8"?>
<opml version="2.0">
  <head><title>Test Feeds</title></head>
  <body>
    <outline text="Tech" title="Tech">
      <outline type="rss" text="simonwillison.net" title="simonwillison.net"
               xmlUrl="https://simonwillison.net/atom/everything/"
               htmlUrl="https://simonwillison.net"/>
      <outline type="rss" text="paulgraham.com" title="paulgraham.com"
               xmlUrl="http://www.aaronsw.com/2002/feeds/pgessays.rss"
               htmlUrl="https://paulgraham.com"/>
    </outline>
    <outline type="rss" text="troyhunt.com" title="troyhunt.com"
             xmlUrl="https://www.troyhunt.com/rss/"
             htmlUrl="https://troyhunt.com"/>
  </body>
</opml>
"""


@pytest.fixture
def sample_opml_path(tmp_path: Path) -> Path:
    p = tmp_path / "test.opml"
    p.write_text(SAMPLE_OPML)
    return p


class TestParseOpml:
    def test_parses_nested_and_flat_feeds(self, sample_opml_path: Path):
        feeds = _parse_opml(sample_opml_path)
        assert len(feeds) == 3
        names = {f.name for f in feeds}
        assert "simonwillison.net" in names
        assert "troyhunt.com" in names

    def test_nested_feeds_have_category(self, sample_opml_path: Path):
        feeds = _parse_opml(sample_opml_path)
        simon = next(f for f in feeds if f.name == "simonwillison.net")
        assert simon.category == "Tech"

    def test_flat_feeds_have_default_category(self, sample_opml_path: Path):
        feeds = _parse_opml(sample_opml_path)
        troy = next(f for f in feeds if f.name == "troyhunt.com")
        assert troy.category == "Blogs"

    def test_missing_file_raises(self, tmp_path: Path):
        with pytest.raises(FileNotFoundError):
            _parse_opml(tmp_path / "nonexistent.opml")

    def test_caching(self, sample_opml_path: Path):
        first = _parse_opml(sample_opml_path)
        second = _parse_opml(sample_opml_path)
        assert first is second


class TestMatchFeed:
    def test_substring_match(self):
        feeds = [
            FeedInfo("simonwillison.net", "url1", "html1"),
            FeedInfo("paulgraham.com", "url2", "html2"),
        ]
        result = _match_feed("simon", feeds)
        assert len(result) == 1
        assert result[0].name == "simonwillison.net"

    def test_fuzzy_match(self):
        feeds = [
            FeedInfo("simonwillison.net", "url1", "html1"),
            FeedInfo("paulgraham.com", "url2", "html2"),
        ]
        result = _match_feed("simonwilison", feeds)  # typo
        assert len(result) >= 1
        assert any(f.name == "simonwillison.net" for f in result)

    def test_no_match(self):
        feeds = [FeedInfo("example.com", "url", "html")]
        result = _match_feed("zzzznotexist", feeds)
        assert len(result) == 0


class TestFetchSingleFeed:
    def test_returns_articles(self):
        mock_entry = MagicMock()
        mock_entry.get = lambda k, d="": {
            "title": "Test Article",
            "link": "https://example.com/post",
            "summary": "A short summary",
        }.get(k, d)
        mock_entry.published_parsed = (2025, 1, 15, 10, 0, 0, 0, 0, 0)
        mock_entry.updated_parsed = None

        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = [mock_entry]

        feed = FeedInfo("test", "https://example.com/feed", "https://example.com")
        with patch("src.tools.rss_feeds.feedparser.parse", return_value=mock_parsed):
            articles = _fetch_single_feed(feed, 5)

        assert len(articles) == 1
        assert articles[0].title == "Test Article"
        assert articles[0].feed_name == "test"
        assert articles[0].published == "2025-01-15T10:00:00Z"

    def test_handles_parse_error(self):
        feed = FeedInfo("bad", "https://bad.example.com/feed", "")
        with patch("src.tools.rss_feeds.feedparser.parse", side_effect=Exception("fail")):
            articles = _fetch_single_feed(feed, 5)
        assert articles == []


class TestListRssFeedsTool:
    def test_lists_all_feeds(self, sample_opml_path: Path):
        with patch("src.tools.rss_feeds._OPML_PATH", sample_opml_path):
            result = list_rss_feeds_tool.invoke({})
        assert "simonwillison.net" in result
        assert "3 total" in result

    def test_filter_by_category(self, sample_opml_path: Path):
        with patch("src.tools.rss_feeds._OPML_PATH", sample_opml_path):
            result = list_rss_feeds_tool.invoke({"category": "Tech"})
        assert "simonwillison.net" in result
        assert "troyhunt.com" not in result


class TestFetchRssArticlesTool:
    def test_no_feed_match_suggests(self, sample_opml_path: Path):
        with patch("src.tools.rss_feeds._OPML_PATH", sample_opml_path):
            result = fetch_rss_articles_tool.invoke({"feed_name": "zzzzz"})
        assert "No feed matching" in result

    def test_fetches_by_name(self, sample_opml_path: Path):
        mock_entry = MagicMock()
        mock_entry.get = lambda k, d="": {
            "title": "Hello World",
            "link": "https://example.com/hello",
            "summary": "Greetings",
        }.get(k, d)
        mock_entry.published_parsed = (2025, 6, 1, 12, 0, 0, 0, 0, 0)
        mock_entry.updated_parsed = None

        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = [mock_entry]

        with (
            patch("src.tools.rss_feeds._OPML_PATH", sample_opml_path),
            patch("src.tools.rss_feeds.feedparser.parse", return_value=mock_parsed),
        ):
            result = fetch_rss_articles_tool.invoke({"feed_name": "simon"})

        assert "Hello World" in result

    def test_hard_timeout_does_not_wait_for_executor_shutdown(self):
        feeds = [
            FeedInfo("feed-1", "https://example.com/feed-1.xml", "https://example.com/1"),
            FeedInfo("feed-2", "https://example.com/feed-2.xml", "https://example.com/2"),
        ]

        class _FakeFuture:
            def done(self):
                return False

        class _FakeExecutor:
            last_instance = None

            def __init__(self, *args, **kwargs):
                self.futures = [_FakeFuture(), _FakeFuture()]
                self.shutdown_args = None
                _FakeExecutor.last_instance = self

            def submit(self, fn, *args, **kwargs):
                return self.futures.pop(0)

            def shutdown(self, wait=True, *, cancel_futures=False):
                self.shutdown_args = (wait, cancel_futures)

        with (
            patch("src.tools.rss_feeds._parse_opml", return_value=feeds),
            patch("src.tools.rss_feeds.ThreadPoolExecutor", _FakeExecutor),
            patch(
                "src.tools.rss_feeds.as_completed",
                side_effect=concurrent.futures.TimeoutError(),
            ),
        ):
            fetch_rss_articles_tool.invoke({})

        assert _FakeExecutor.last_instance is not None
        assert _FakeExecutor.last_instance.shutdown_args == (False, True)


class TestGetFeedsLatestOverviewTool:
    """Tests for the get_feeds_latest_overview_tool."""

    def test_returns_table_with_latest_articles(self, sample_opml_path):
        entry_data = {
            "title": "Latest Post",
            "link": "https://example.com/latest",
            "summary": "A summary",
        }
        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = [
            MagicMock(
                title="Latest Post",
                link="https://example.com/latest",
                published_parsed=(2025, 6, 15, 10, 0, 0, 0, 0, 0),
                **{"get.side_effect": lambda k, d="": entry_data.get(k, d)},
            )
        ]
        # Ensure hasattr checks work
        mock_parsed.entries[0].updated_parsed = None

        with (
            patch("src.tools.rss_feeds._OPML_PATH", sample_opml_path),
            patch("src.tools.rss_feeds.feedparser.parse", return_value=mock_parsed),
        ):
            result = get_feeds_latest_overview_tool.invoke({})

        assert "Latest from" in result
        assert "Latest Post" in result
        assert "2025-06-15" in result
        # Should be a table format
        assert "| #" in result

    def test_shows_no_articles_for_empty_feeds(self, sample_opml_path):
        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = []

        with (
            patch("src.tools.rss_feeds._OPML_PATH", sample_opml_path),
            patch("src.tools.rss_feeds.feedparser.parse", return_value=mock_parsed),
        ):
            result = get_feeds_latest_overview_tool.invoke({})

        assert "_(no articles)_" in result

    def test_category_filter(self, sample_opml_path):
        mock_parsed = MagicMock()
        mock_parsed.bozo = False
        mock_parsed.entries = []

        with (
            patch("src.tools.rss_feeds._OPML_PATH", sample_opml_path),
            patch("src.tools.rss_feeds.feedparser.parse", return_value=mock_parsed),
        ):
            result = get_feeds_latest_overview_tool.invoke({"category": "NonExistent"})

        assert "No feeds found in category" in result


class TestRealOpml:
    """Tests against the actual OPML file shipped with the project."""

    def test_real_opml_parses(self):
        real_path = Path(__file__).parent.parent / "src" / "config" / "hn-popular-blogs-2025.opml"
        if not real_path.exists():
            pytest.skip("Real OPML file not found")
        feeds = _parse_opml(real_path)
        assert len(feeds) > 50
        names = {f.name for f in feeds}
        assert "simonwillison.net" in names
        assert "paulgraham.com" in names
