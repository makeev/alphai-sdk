"""Search wire contract, typed interpretation and cursor/error behavior in both clients."""

from datetime import date, datetime, timezone

import httpx
import pytest
import respx

from alphai import (
    AsyncClient,
    BadRequestError,
    Client,
    NewsCategory,
    NewsSearchPage,
    NewsSearchQueryInfo,
    PermissionDeniedError,
    RateLimitError,
    SearchMatch,
    ServerError,
)

from .conftest import BASE_URL

ENDPOINT = f"{BASE_URL}/api/news/search/"


@pytest.fixture(params=["sync", "async"])
async def sdk(request):
    if request.param == "async":
        async with AsyncClient(api_key="ak_live_test", max_retries=0) as client:
            yield client
    else:
        with Client(api_key="ak_live_test", max_retries=0) as client:
            yield client


async def search(sdk, **kwargs):
    if isinstance(sdk, AsyncClient):
        return await sdk.news.search(**kwargs)
    return sdk.news.search(**kwargs)


def response(article, *, mode="strict", cursor=None):
    empty = mode in {"no_match", "no_terms"}
    results = (
        []
        if empty
        else [
            {
                **article,
                "search_match": {
                    "score": 0.87,
                    "terms_matched": 2 if mode == "broadened" else None,
                    "context": None if mode == "strict" else "**Jane** **Street** coverage",
                    "future_field": "preserved",
                },
            }
        ]
    )
    return {
        "results": results,
        "count": len(results),
        "matched": 0 if empty else 24,
        "next_cursor": cursor,
        "query": {
            "mode": mode,
            "sort": "relevance",
            "terms": ["jane", "street"],
            "required_terms": [],
            "optional_terms": [],
            "window_from": "2026-09-01T00:00:00Z",
            "note": "Interpretation note.",
        },
    }


@pytest.mark.parametrize("mode", ["strict", "broadened", "no_match", "no_terms"])
@respx.mock
async def test_typed_interpretation(sdk, article, mode):
    route = respx.get(ENDPOINT).respond(200, json=response(article, mode=mode))
    page = await search(sdk, query="Jane Street")
    assert isinstance(page, NewsSearchPage)
    assert isinstance(page.query, NewsSearchQueryInfo)
    assert page.query.mode == mode
    assert page.query.window_from == datetime(2026, 9, 1, tzinfo=timezone.utc)
    assert page.query.note == "Interpretation note."
    assert dict(route.calls[0].request.url.params) == {"q": "Jane Street"}
    assert page.caught_up and not page.has_more
    if mode in {"no_match", "no_terms"}:
        assert page.results == [] and page.matched == page.count == 0
    else:
        match = page.results[0].search_match
        assert isinstance(match, SearchMatch)
        assert match.score == 0.87
        assert match.terms_matched == (2 if mode == "broadened" else None)
        assert match.model_extra == {"future_field": "preserved"}


@respx.mock
async def test_all_filters_and_cursor_are_preserved(sdk, article):
    route = respx.get(ENDPOINT).mock(
        side_effect=[
            httpx.Response(200, json=response(article, cursor="opaque+/=")),
            httpx.Response(200, json=response(article)),
        ]
    )
    filters = {
        "query": '"going concern" -resolved OR liquidity',
        "symbol": "NVDA",
        "category": [NewsCategory.EARNINGS, "other"],
        "source_type": ["sec_form8k", "sec_form6k"],
        "min_relevance": 4,
        "collapse_stories": True,
        "page_size": 20,
        "from_date": date(2026, 9, 1),
        "to_date": datetime(2026, 9, 23, 12, tzinfo=timezone.utc),
    }
    first = await search(sdk, **filters)
    assert first.has_more
    second = await search(sdk, cursor=first.next_cursor, **filters)
    assert not second.has_more
    params = route.calls[0].request.url.params
    assert params["q"] == filters["query"]
    assert params["symbol"] == "NVDA"
    assert params.get_list("category") == ["earnings", "other"]
    assert params.get_list("source_type") == ["sec_form8k", "sec_form6k"]
    assert params["min_relevance"] == "4" and params["collapse"] == "story"
    assert params["page_size"] == "20"
    assert params["from_date"] == "2026-09-01"
    assert params["to_date"] == "2026-09-23T12:00:00+00:00"
    continued = route.calls[1].request.url.params
    assert continued["cursor"] == "opaque+/="
    assert continued.remove("cursor") == params


@respx.mock
async def test_item_single_source_and_date_strings(sdk, article):
    route = respx.get(ENDPOINT).respond(200, json=response(article))
    await search(
        sdk,
        query="chief executive",
        source_type="sec_form8k",
        item="5.02",
        category="corporate_actions",
        from_date="2026-09-01",
        to_date="2026-09-23",
    )
    params = route.calls[0].request.url.params
    assert params.get_list("source_type") == ["sec_form8k"]
    assert params["item"] == "5.02"
    assert params["to_date"] == "2026-09-23"
    assert "collapse" not in params and "sort" not in params


@pytest.mark.parametrize(
    "status,error,reason",
    [
        (400, BadRequestError, "invalid_cursor"),
        (403, PermissionDeniedError, "archive_horizon"),
        (429, RateLimitError, "rate_limited"),
        (503, ServerError, "search_unavailable"),
    ],
)
@respx.mock
async def test_errors_are_not_empty_results(sdk, status, error, reason):
    route = respx.get(ENDPOINT).respond(
        status, json={"message": "Search failed", "extra": {"reason": reason}}
    )
    with pytest.raises(error) as caught:
        await search(sdk, query="Jane Street", cursor="invalid")
    assert caught.value.extra["reason"] == reason
    assert route.call_count == 1


def test_optional_query_metadata_and_missing_search_match(article):
    page = NewsSearchPage.model_validate(
        {
            "results": [article],
            "count": 1,
            "matched": 1,
            "query": {"mode": "strict", "sort": "published", "terms": ["common"]},
        }
    )
    assert page.query.window_from is None
    assert page.query.required_terms == []
    assert page.results[0].search_match is None
