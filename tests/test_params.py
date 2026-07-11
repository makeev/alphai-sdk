"""Query-param assembly: category forms, collapse, None-dropping."""

from __future__ import annotations

import httpx
import respx

from alphai import Client, NewsCategory

from .conftest import BASE_URL, page


def _capture(client: Client, **kwargs: object) -> httpx.QueryParams:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([], None))
    )
    client.news.list(**kwargs)  # type: ignore[arg-type]
    return route.calls[0].request.url.params


@respx.mock
def test_category_single_string(client: Client) -> None:
    params = _capture(client, category="earnings")
    assert params.get_list("category") == ["earnings"]


@respx.mock
def test_category_enum(client: Client) -> None:
    params = _capture(client, category=NewsCategory.EARNINGS)
    assert params.get_list("category") == ["earnings"]


@respx.mock
def test_category_list_mixed(client: Client) -> None:
    params = _capture(client, category=[NewsCategory.EARNINGS, "insider"])
    assert params.get_list("category") == ["earnings", "insider"]


@respx.mock
def test_exclude_categories(client: Client) -> None:
    params = _capture(client, exclude_categories=["crypto", "other"])
    assert params.get_list("exclude_categories") == ["crypto", "other"]


@respx.mock
def test_collapse_stories_maps_to_story(client: Client) -> None:
    params = _capture(client, collapse_stories=True)
    assert params["collapse"] == "story"


@respx.mock
def test_collapse_false_omitted(client: Client) -> None:
    params = _capture(client, collapse_stories=False)
    assert "collapse" not in params


@respx.mock
def test_min_relevance_and_symbol(client: Client) -> None:
    params = _capture(client, symbol="NVDA", min_relevance=8)
    assert params["symbol"] == "NVDA"
    assert params["min_relevance"] == "8"


@respx.mock
def test_none_values_dropped(client: Client) -> None:
    params = _capture(client)
    assert params == httpx.QueryParams("")


@respx.mock
def test_page_size_passed_through(client: Client) -> None:
    params = _capture(client, page_size=50)
    assert params["page_size"] == "50"


@respx.mock
def test_page_size_omitted_by_default(client: Client) -> None:
    params = _capture(client)
    assert "page_size" not in params


@respx.mock
def test_insider_page_size_passed_through(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(200, json=page([], None))
    )
    client.news.insider(page_size=50)
    assert route.calls[0].request.url.params["page_size"] == "50"


def test_insider_params_include_min_relevance():
    from alphai import _requests as rq

    params = rq.build_news_insider_params(
        symbol="NVDA", min_relevance=7, cursor=None, page_size=None
    )
    assert params["min_relevance"] == 7
    assert params["symbol"] == "NVDA"
