"""News endpoint coverage (sync) via respx."""

from __future__ import annotations

import httpx
import respx

from alphai import Client

from .conftest import BASE_URL, page


@respx.mock
def test_news_list(client: Client, article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([article], "cursor2"))
    )
    result = client.news.list(symbol="NVDA")
    assert route.called
    assert result.has_more is True
    assert result.next_cursor == "cursor2"
    assert result.results[0].uid == "788e477c66f3849b"


@respx.mock
def test_news_trending(client: Client, article: dict, insider_article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        return_value=httpx.Response(200, json=[article, insider_article])
    )
    items = client.news.trending()
    assert len(items) == 2
    assert items[0].title.startswith("NVIDIA")


@respx.mock
def test_news_insider(client: Client, insider_article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(200, json=page([insider_article], None))
    )
    result = client.news.insider(symbol="NVDA")
    assert result.has_more is False
    assert result.results[0].enrichment.category == "insider"


@respx.mock
def test_news_get(client: Client, article: dict) -> None:
    uid = "788e477c66f3849b"
    respx.get(f"{BASE_URL}/api/news/{uid}/").mock(return_value=httpx.Response(200, json=article))
    art = client.news.get(uid)
    assert art.uid == uid
    assert art.enrichment.relevance_score == 9


@respx.mock
def test_news_related(client: Client, article: dict, insider_article: dict) -> None:
    uid = "788e477c66f3849b"
    respx.get(f"{BASE_URL}/api/news/{uid}/related/").mock(
        return_value=httpx.Response(200, json={"results": [insider_article]})
    )
    related = client.news.related(uid)
    assert len(related) == 1
    assert related[0].uid == "a1b2c3d4e5f60718"


@respx.mock
def test_collapse_stories_populates_story_fields(client: Client, article: dict) -> None:
    collapsed = {
        **article,
        "story_id": "788e477c66f3849b",
        "sources_count": 7,
        "sources": ["reuters.com", "apnews.com"],
    }
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([collapsed], None))
    )
    result = client.news.list(collapse_stories=True)
    item = result.results[0]
    assert item.story_id == "788e477c66f3849b"
    assert item.sources_count == 7
    assert item.sources == ["reuters.com", "apnews.com"]
