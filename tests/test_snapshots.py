"""Brief/Radar contract tests using response shapes captured from the live API."""

from __future__ import annotations

import inspect
from datetime import date, datetime
from typing import Any

import httpx
import pytest
import respx

from alphai import (
    AsyncClient,
    Client,
    ConflictError,
    InvalidResponseError,
    RateLimitError,
    ServerError,
)

from .conftest import BASE_URL, load


@pytest.fixture(params=[False, True], ids=["sync", "async"])
async def api(request: Any) -> Any:
    cls = AsyncClient if request.param else Client
    client = cls(api_key="ak_live_test", backoff_factor=0, max_retries=2)
    yield client
    result = client.close()
    if inspect.isawaitable(result):
        await result


async def resolve(value: Any) -> Any:
    return await value if inspect.isawaitable(value) else value


async def collect(iterator: Any) -> list[Any]:
    if hasattr(iterator, "__aiter__"):
        return [item async for item in iterator]
    return list(iterator)


@respx.mock
async def test_brief_wire_contract(api: Any) -> None:
    data = load("brief")
    data["future_field"] = {"preserved": True}
    route = respx.get(f"{BASE_URL}/api/news/brief/").respond(200, json=data)
    brief = await resolve(
        api.news.brief(tickers=[" nvda", "AMD", "NVDA", "BTC-USD"], hours=168, limit=2)
    )
    assert dict(route.calls.last.request.url.params) == {
        "tickers": "NVDA,AMD,BTC-USD",
        "hours": "168",
        "limit": "2",
    }
    assert isinstance(brief.generated_at, datetime)
    assert brief.window_start <= brief.window_end == brief.generated_at
    assert brief.unknown_tickers == ["SDK-UNKNOWN"]
    assert brief.events_truncated and brief.filings_truncated
    assert isinstance(brief.upcoming_earnings[0].report_date, date)
    assert brief.events[0].matched_tickers
    assert brief.model_extra["future_field"] == {"preserved": True}


@respx.mock
async def test_brief_empty_sections_and_missing_date_are_not_filled(api: Any) -> None:
    data = load("brief")
    data.update(
        events=[], filings=[], upcoming_earnings=[], events_truncated=False, filings_truncated=False
    )
    respx.get(f"{BASE_URL}/api/news/brief/").respond(200, json=data)
    brief = await resolve(api.news.brief(tickers="SDK-UNKNOWN"))
    assert brief.events == brief.filings == brief.upcoming_earnings == []


@pytest.mark.parametrize(
    "params",
    [
        {"tickers": []},
        {"tickers": ""},
        {"tickers": "NVDA,"},
        {"tickers": ["X" * 21]},
        {"tickers": [str(i) for i in range(101)]},
        {"tickers": ["NVDA"], "hours": 0},
        {"tickers": ["NVDA"], "hours": 169},
        {"tickers": ["NVDA"], "limit": 21},
        {"tickers": ["NVDA"], "limit": 1.5},
    ],
)
@respx.mock
async def test_invalid_brief_never_spends_a_request(api: Any, params: Any) -> None:
    with pytest.raises(ValueError):
        await resolve(api.news.brief(**params))
    assert not respx.calls


@respx.mock
async def test_radar_wire_contract_and_nulls(api: Any) -> None:
    data = load("radar")
    data["results"][0].update(news_z=None, sent_delta=None)
    data["results"][0]["sent"].update(value=None, coverage=None, reason="insufficient_stories")
    route = respx.get(f"{BASE_URL}/api/signals/snapshot/").respond(200, json=data)
    page = await resolve(
        api.radar.snapshot(
            window="4h",
            scope="market",
            market="us_equity",
            tickers=[" nvda", "AMD", "NVDA"],
            search="n",
            sort="sentiment_change",
            order="asc",
            sentiment="mixed",
            min_z=0,
            limit=2,
            offset=0,
            cursor="opaque-signed-token",
        )
    )
    params = dict(route.calls.last.request.url.params)
    assert params == {
        "window": "4h",
        "scope": "market",
        "market": "us_equity",
        "tickers": "NVDA,AMD",
        "search": "N",
        "sort": "sentiment_change",
        "order": "asc",
        "sentiment": "mixed",
        "min_z": "0",
        "limit": "2",
        "offset": "0",
        "cursor": "opaque-signed-token",
    }
    assert isinstance(page.as_of, datetime)
    assert page.freshness.mode == "live"
    assert page.access.delay_seconds == 3600
    assert page.results[0].news_z is None
    assert page.results[0].sent.value is None
    assert page.results[0].sent.reason == "insufficient_stories"
    assert page.preview_reference_at is None


@respx.mock
async def test_radar_empty_watchlist_and_exact_ticker(api: Any) -> None:
    data = load("radar")
    data.update(
        results=[],
        total=0,
        next_cursor=None,
        next_offset=None,
        watchlist_coverage={"no_recent_news": [], "not_in_snapshot": []},
    )
    data["access"].update(scope="watchlist", watchlist_count=0)
    route = respx.get(f"{BASE_URL}/api/signals/snapshot/").respond(200, json=data)
    page = await resolve(api.radar.snapshot(scope="watchlist", ticker=" btc-usd "))
    assert page.results == []
    assert page.access.watchlist_count == 0
    assert route.calls.last.request.url.params["ticker"] == "BTC-USD"


@pytest.mark.parametrize(
    "params",
    [
        {"tickers": []},
        {"ticker": "A", "tickers": ["B"]},
        {"ticker": " "},
        {"offset": 1, "cursor": "x"},
        {"min_z": float("nan")},
        {"min_z": float("inf")},
        {"min_z": 9},
        {"limit": 101},
        {"limit": True},
        {"offset": -1},
        {"window": "1h"},
        {"tickers": ["X" * 33]},
        {"tickers": [f"{i:032}" for i in range(500)]},
        {"cursor": "x" * 4097},
    ],
)
@respx.mock
async def test_invalid_radar_never_spends_a_request(api: Any, params: Any) -> None:
    with pytest.raises(ValueError):
        await resolve(api.radar.snapshot(**params))
    assert not respx.calls


@respx.mock
async def test_radar_iteration_pins_filters_and_consumes_tickers_once(api: Any) -> None:
    first = load("radar")
    second = {**first, "next_cursor": None, "previous_cursor": "previous", "offset": 2}
    route = respx.get(f"{BASE_URL}/api/signals/snapshot/").mock(
        side_effect=[httpx.Response(200, json=first), httpx.Response(200, json=second)]
    )
    readings = await collect(api.radar.iter(tickers=iter(["NVDA", "AMD"]), limit=2, offset=1))
    assert len(readings) == 4
    requests = [call.request.url.params for call in route.calls]
    assert requests[0]["offset"] == "1" and "offset" not in requests[1]
    assert requests[1]["cursor"] == first["next_cursor"]
    assert requests[0]["tickers"] == requests[1]["tickers"] == "NVDA,AMD"
    assert requests[0]["limit"] == requests[1]["limit"] == "2"


@respx.mock
async def test_conflict_is_not_retried_or_restarted(api: Any) -> None:
    route = respx.get(f"{BASE_URL}/api/signals/snapshot/").mock(
        side_effect=[
            httpx.Response(200, json=load("radar")),
            httpx.Response(409, json={"detail": "Snapshot expired"}),
        ]
    )
    with pytest.raises(ConflictError, match="Snapshot expired") as error:
        await collect(api.radar.iter(limit=2))
    assert error.value.status == 409
    assert route.call_count == 2


@pytest.mark.parametrize("changed", [True, False])
@respx.mock
async def test_iterator_rejects_snapshot_switches_and_cursor_cycles(
    api: Any, changed: bool
) -> None:
    first = load("radar")
    second = {**first, "snapshot_id": "different" if changed else first["snapshot_id"]}
    respx.get(f"{BASE_URL}/api/signals/snapshot/").mock(
        side_effect=[httpx.Response(200, json=first), httpx.Response(200, json=second)]
    )
    with pytest.raises(InvalidResponseError, match=r"changed|repeated"):
        await collect(api.radar.iter())


@pytest.mark.parametrize(
    "caps,expected_calls,expected_items",
    [
        ({"max_items": 0}, 0, 0),
        ({"max_pages": 0}, 0, 0),
        ({"max_items": 1}, 1, 1),
        ({"max_pages": 1}, 1, 2),
    ],
)
@respx.mock
async def test_iteration_bounds(
    api: Any, caps: Any, expected_calls: int, expected_items: int
) -> None:
    route = respx.get(f"{BASE_URL}/api/signals/snapshot/").respond(200, json=load("radar"))
    assert len(await collect(api.radar.iter(**caps))) == expected_items
    assert route.call_count == expected_calls


@pytest.mark.parametrize("status,exception", [(503, ServerError), (429, RateLimitError)])
@respx.mock
async def test_unavailable_and_rate_limits_keep_bounded_retry_policy(
    api: Any, status: int, exception: Any
) -> None:
    route = respx.get(f"{BASE_URL}/api/signals/snapshot/").respond(
        status, json={"message": "Try later"}, headers={"Retry-After": "0"}
    )
    with pytest.raises(exception):
        await resolve(api.radar.snapshot())
    assert route.call_count == 3
