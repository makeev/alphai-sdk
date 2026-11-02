"""``news.insider_clusters`` — insider cluster buys (``GET /api/news/insider/clusters/``)."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx

from alphai import (
    AsyncClient,
    Client,
    InsiderCluster,
    InsiderClustersPage,
    PermissionDeniedError,
)

from .conftest import BASE_URL, load

URL = f"{BASE_URL}/api/news/insider/clusters/"


@respx.mock
def test_page_parses_clusters_buyers_filings_and_meta(client: Client) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=load("insider_clusters")))
    page = client.news.insider_clusters()
    assert route.called
    # No filter given: nothing is sent, the server's defaults apply.
    assert not route.calls[0].request.url.params
    assert isinstance(page, InsiderClustersPage)
    assert len(page.results) == 2 and page.next_cursor

    rapp = page.results[0]
    assert isinstance(rapp, InsiderCluster)
    assert rapp.ticker == "RAPP" and rapp.cik == 2012593
    assert rapp.pattern == "open_market" and rapp.pattern_reasons == []
    assert rapp.buyers == rapp.buyers_total == len(rapp.buyers_detail) == 7
    assert rapp.officer_director_buyers == 7 and rapp.ten_percent_owner_buyers == 0
    assert rapp.total_usd == Decimal("22023904.35") and not rapp.value_partial
    assert rapp.window_start <= rapp.window_end
    assert rapp.known_at.tzinfo is not None
    lead = rapp.buyers_detail[0]
    assert lead.role == "independent" and lead.reason is None and lead.duplicate_of is None
    assert lead.is_director and not lead.is_officer and lead.title == ""
    assert lead.usd == Decimal("20359080.00") and lead.fills == 4
    assert lead.news_uids == ["f84212f3b1e73cd0"]
    cfo = rapp.buyers_detail[3]
    assert cfo.is_officer and cfo.title == "Chief Financial Officer"
    assert len(rapp.filings_detail) == rapp.filings == 7
    filing = rapp.filings_detail[0]
    assert filing.accession_number == "0001193125-26-428018"
    assert filing.filed_at.tzinfo is not None
    assert filing.sec_url.startswith("https://www.sec.gov/Archives/edgar/data/2012593/")

    accv = page.results[1]
    assert accv.pattern == "plan_or_offering"
    assert accv.buyers == 0 and accv.buyers_total == 5
    assert "off_market_buyers" in accv.pattern_reasons
    assert {b.role for b in accv.buyers_detail} == {"plan_like"}
    assert {b.reason for b in accv.buyers_detail} == {"offering"}
    assert accv.distinct_dates == accv.distinct_prices == 1

    meta = page.meta
    assert meta.as_of.tzinfo is not None
    assert meta.coverage_since is not None and meta.coverage_since.year == 2025
    assert meta.episode_gap_days == 10 and meta.episode_max_days == 30
    assert meta.research_only and not meta.point_in_time


@respx.mock
def test_sends_every_filter(client: Client) -> None:
    route = respx.get(URL).mock(return_value=httpx.Response(200, json=load("insider_clusters")))
    client.news.insider_clusters(
        days=90,
        min_buyers=3,
        min_usd=100_000,
        pattern="all",
        symbol="RAPP",
        sort="value",
        cursor="c1",
        page_size=20,
    )
    params = route.calls[0].request.url.params
    assert params["days"] == "90"
    assert params["min_buyers"] == "3"
    assert params["min_usd"] == "100000"
    assert params["pattern"] == "all"
    assert params["symbol"] == "RAPP"
    assert params["sort"] == "value"
    assert params["cursor"] == "c1"
    assert params["page_size"] == "20"


@pytest.mark.parametrize(
    "kwargs",
    [
        {"days": 0},
        {"days": 91},
        {"min_buyers": 1},
        {"min_buyers": 11},
        {"min_usd": -1},
        {"page_size": 0},
        {"page_size": 51},
        {"pattern": "everything"},
        {"sort": "newest"},
    ],
)
def test_ranges_and_enums_are_validated_locally(client: Client, kwargs: dict[str, object]) -> None:
    with respx.mock(assert_all_called=False) as mock:
        route = mock.get(URL)
        with pytest.raises(ValueError):
            client.news.insider_clusters(**kwargs)  # type: ignore[arg-type]
        assert not route.called


@respx.mock
def test_iter_follows_cursor_threads_filters_and_honors_caps(client: Client) -> None:
    page = load("insider_clusters")
    last = {**page, "results": page["results"][:1], "next_cursor": None}
    route = respx.get(URL).mock(
        side_effect=[httpx.Response(200, json=page), httpx.Response(200, json=last)]
    )
    tickers = [c.ticker for c in client.news.insider_clusters_iter(days=60, sort="buyers")]
    assert tickers == ["RAPP", "ACCV", "RAPP"]
    assert "cursor" not in route.calls[0].request.url.params
    assert route.calls[1].request.url.params["cursor"] == page["next_cursor"]
    for call in route.calls:
        assert call.request.url.params["days"] == "60"
        assert call.request.url.params["sort"] == "buyers"

    route.side_effect = [httpx.Response(200, json=page), httpx.Response(200, json=last)]
    assert len(list(client.news.insider_clusters_iter(max_items=1))) == 1
    route.side_effect = [httpx.Response(200, json=page), httpx.Response(200, json=last)]
    assert len(list(client.news.insider_clusters_iter(max_pages=1))) == 2


@respx.mock
def test_archive_horizon_is_permission_denied(client: Client) -> None:
    respx.get(URL).mock(
        return_value=httpx.Response(
            403,
            json={
                "message": "Archive horizon exceeded.",
                "extra": {"reason": "archive_horizon", "tier": "free", "archive_days": 30},
            },
        )
    )
    with pytest.raises(PermissionDeniedError):
        client.news.insider_clusters(days=90)


@respx.mock
async def test_async_page_and_iter() -> None:
    page = load("insider_clusters")
    last = {**page, "results": page["results"][:1], "next_cursor": None}
    route = respx.get(URL).mock(
        side_effect=[
            httpx.Response(200, json=page),
            httpx.Response(200, json=page),
            httpx.Response(200, json=last),
        ]
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        first = await client.news.insider_clusters(pattern="all", page_size=2)
        assert first.results[0].ticker == "RAPP" and first.meta.research_only
        assert route.calls[0].request.url.params["pattern"] == "all"
        tickers = [c.ticker async for c in client.news.insider_clusters_iter(pattern="all")]
        assert tickers == ["RAPP", "ACCV", "RAPP"]
        assert route.calls[-1].request.url.params["cursor"] == page["next_cursor"]
