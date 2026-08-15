"""Query-param assembly: category forms, collapse, None-dropping."""

from __future__ import annotations

from typing import Any

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


@respx.mock
def test_sort_passed_through(client: Client) -> None:
    params = _capture(client, sort="ingested")
    assert params["sort"] == "ingested"


@respx.mock
def test_sort_omitted_by_default(client: Client) -> None:
    # The server default is `published`; sending it explicitly would only make
    # cached URLs differ for no reason.
    params = _capture(client)
    assert "sort" not in params


@respx.mock
def test_iter_threads_sort_onto_every_page(client: Client, article: Any) -> None:
    # Cursors are mode-specific: a run that dropped `sort` after page one would
    # replay an ingested cursor into published mode and get a 400. The second
    # response also pins the delta stop condition - in ingested mode a caught-up
    # poll returns an empty page with the SAME cursor, and the paginator's
    # repeated-cursor guard is what ends the loop (there is no null cursor).
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([article], "cur1")),
            httpx.Response(200, json=page([], "cur1")),
        ]
    )
    assert len(list(client.news.iter(sort="ingested"))) == 1
    assert len(route.calls) == 2
    for call in route.calls:
        assert call.request.url.params["sort"] == "ingested"


# --- from_date / to_date window (v0.5.0) -----------------------------------


def _capture_insider(client: Client, **kwargs: object) -> httpx.QueryParams:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(200, json=page([], None))
    )
    client.news.insider(**kwargs)  # type: ignore[arg-type]
    return route.calls[0].request.url.params


@respx.mock
def test_date_object_serializes_bare(client: Client) -> None:
    # The bare form is load-bearing: the server reads a bare to_date as the
    # END of that day, so a date object must never grow a time part.
    from datetime import date

    params = _capture(client, from_date=date(2026, 7, 1), to_date=date(2026, 7, 31))
    assert params["from_date"] == "2026-07-01"
    assert params["to_date"] == "2026-07-31"


@respx.mock
def test_datetime_is_the_exact_instant(client: Client) -> None:
    from datetime import datetime, timezone

    params = _capture(
        client,
        from_date=datetime(2026, 7, 1, 9, 30),
        to_date=datetime(2026, 7, 1, 16, 0, tzinfo=timezone.utc),
    )
    assert params["from_date"] == "2026-07-01T09:30:00"
    assert params["to_date"] == "2026-07-01T16:00:00+00:00"


@respx.mock
def test_window_string_passes_through(client: Client) -> None:
    # Any server-accepted ISO spelling must survive verbatim - the SDK
    # serializes its own types but never rewrites a caller's string.
    params = _capture(client, from_date="2026-07-01", to_date="2026-07-01T23:59:59.999999Z")
    assert params["from_date"] == "2026-07-01"
    assert params["to_date"] == "2026-07-01T23:59:59.999999Z"


@respx.mock
def test_window_omitted_by_default(client: Client) -> None:
    params = _capture(client)
    assert "from_date" not in params
    assert "to_date" not in params


@respx.mock
def test_insider_takes_the_window(client: Client) -> None:
    from datetime import date

    params = _capture_insider(client, from_date=date(2026, 7, 1), to_date="2026-07-31")
    assert params["from_date"] == "2026-07-01"
    assert params["to_date"] == "2026-07-31"


@respx.mock
def test_iter_threads_the_window_onto_every_page(client: Client, article: Any) -> None:
    # A window dropped after page one would silently widen the walk back into
    # history the caller asked to bound.
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([article], "cur1")),
            httpx.Response(200, json=page([article], None)),
        ]
    )
    assert len(list(client.news.iter(from_date="2026-07-01", to_date="2026-07-31"))) == 2
    assert len(route.calls) == 2
    for call in route.calls:
        assert call.request.url.params["from_date"] == "2026-07-01"
        assert call.request.url.params["to_date"] == "2026-07-31"
