"""Cursor auto-pagination: drain, max_items, max_pages, insider_iter."""

from __future__ import annotations

import httpx
import respx

from alphai import Client

from .conftest import BASE_URL, page


def _two_pages(article: dict, insider_article: dict) -> list[httpx.Response]:
    return [
        httpx.Response(200, json=page([article, insider_article], "cursor2")),
        httpx.Response(200, json=page([article], None)),
    ]


@respx.mock
def test_iter_drains_all_pages(client: Client, article: dict, insider_article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(side_effect=_two_pages(article, insider_article))
    items = list(client.news.iter())
    assert len(items) == 3  # 2 from page 1 + 1 from page 2, then next_cursor None


@respx.mock
def test_iter_max_items_caps(client: Client, article: dict, insider_article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(side_effect=_two_pages(article, insider_article))
    items = list(client.news.iter(max_items=2))
    assert len(items) == 2


@respx.mock
def test_iter_max_pages_caps(client: Client, article: dict, insider_article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=_two_pages(article, insider_article)
    )
    items = list(client.news.iter(max_pages=1))
    assert len(items) == 2  # only page 1 fetched
    assert route.call_count == 1


@respx.mock
def test_iter_forwards_cursor(client: Client, article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([article], "CURSOR_X")),
            httpx.Response(200, json=page([article], None)),
        ]
    )
    list(client.news.iter())
    assert route.call_count == 2
    # first page omits cursor, second page sends the cursor from page 1
    assert b"cursor" not in route.calls[0].request.url.query
    assert b"cursor=CURSOR_X" in route.calls[1].request.url.query


@respx.mock
def test_insider_iter(client: Client, insider_article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/insider/").mock(
        side_effect=[
            httpx.Response(200, json=page([insider_article], "c2")),
            httpx.Response(200, json=page([insider_article], None)),
        ]
    )
    items = list(client.news.insider_iter(symbol="NVDA"))
    assert len(items) == 2


# --- ingested mode: termination must not key on the cursor -----------------
#
# In ingested mode `next_cursor` is ALWAYS set, and a caught-up poll parks the
# position at the GLOBAL feed head — which advances whenever any row lands, not
# just one matching the caller's filter. So both "cursor is null" and "cursor
# stopped moving" are unreliable stop signals there; only an empty page is.


@respx.mock
def test_ingested_empty_page_is_caught_up(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([], "STILL_SET"))
    )
    result = client.news.list(sort="ingested")
    assert result.next_cursor == "STILL_SET"
    assert result.caught_up is True
    assert result.has_more is False  # regression: was True for every poll


@respx.mock
def test_ingested_non_empty_page_has_more(client: Client, article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([article], "c1"))
    )
    result = client.news.list(sort="ingested")
    assert result.caught_up is False
    assert result.has_more is True


@respx.mock
def test_published_mode_semantics_unchanged(client: Client, article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([article], "c1")),
            httpx.Response(200, json=page([article], None)),
        ]
    )
    assert client.news.list().has_more is True
    assert client.news.list().has_more is False


@respx.mock
def test_ingested_iter_stops_on_empty_page_despite_moving_cursor(
    client: Client, article: dict
) -> None:
    """The race that burned rate-limit budget: caught up, but the head keeps
    advancing because unrelated rows are being ingested."""
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([article], "head_1")),
            httpx.Response(200, json=page([], "head_2")),  # caught up, cursor moved
            httpx.Response(200, json=page([], "head_3")),  # must never be reached
        ]
    )
    items = list(client.news.iter(symbol="RARE", sort="ingested"))
    assert len(items) == 1
    assert route.call_count == 2


@respx.mock
def test_insider_iter_forwards_sort(client: Client, insider_article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        side_effect=[
            httpx.Response(200, json=page([insider_article], "c2")),
            httpx.Response(200, json=page([], "c3")),
        ]
    )
    items = list(client.news.insider_iter(symbol="NVDA", sort="ingested"))
    assert len(items) == 1
    assert b"sort=ingested" in route.calls[0].request.url.query
