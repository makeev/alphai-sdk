"""``client.coverage()`` — the coverage passport (``GET /api/coverage/``)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
import pytest
import respx

from alphai import AsyncClient, Client, Coverage, ServerError

from .conftest import BASE_URL, load

SOURCES = [
    "publisher_news",
    "sec_form4",
    "sec_form8k",
    "sec_form6k",
    "earnings_reads",
    "earnings_schedule",
    "economic_calendar",
]


@respx.mock
def test_coverage_parses_every_source(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/coverage/").mock(
        return_value=httpx.Response(200, json=load("coverage"))
    )
    cov = client.coverage()
    assert route.called
    assert isinstance(cov, Coverage)
    assert cov.research_only is True
    assert cov.as_of == datetime(2026, 10, 9, 3, 50, 0, 752146, tzinfo=timezone.utc)
    assert [s.source for s in cov.sources] == SOURCES

    news = cov.by_source("publisher_news")
    assert news is not None
    assert news.rows_total > 0
    assert news.archive_days is not None
    assert (news.archive_days.free, news.archive_days.basic, news.archive_days.pro) == (
        30,
        90,
        180,
    )
    assert news.channels is not None
    assert [c.channel for c in news.channels] == ["gkg", "rss"]
    assert all(isinstance(c.stale, bool) for c in news.channels)


@respx.mock
def test_coverage_nullable_fields(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/coverage/").mock(
        return_value=httpx.Response(200, json=load("coverage"))
    )
    cov = client.coverage()
    eightk = cov.by_source("sec_form8k")
    assert eightk is not None
    assert eightk.first_row_at is not None
    assert eightk.history_note
    assert eightk.limits
    assert eightk.channels is None  # channels are publisher_news only

    reads = cov.by_source("earnings_reads")
    assert reads is not None and reads.archive_days is None  # gate does not apply

    calendar = cov.by_source("economic_calendar")
    assert calendar is not None and calendar.stale_after_seconds is None

    assert cov.by_source("nonexistent") is None


@respx.mock
def test_coverage_empty_source_keeps_null_dates(client: Client) -> None:
    body = load("coverage")
    body["sources"][3] = {
        "source": "sec_form6k",
        "first_row_at": None,
        "last_row_at": None,
        "last_ingested_at": None,
        "rows_total": 0,
        "cadence": "x",
        "history_note": "y",
        "limits": [],
        "archive_days": None,
        "stale": True,
        "stale_after_seconds": 259200,
        "channels": None,
    }
    respx.get(f"{BASE_URL}/api/coverage/").mock(return_value=httpx.Response(200, json=body))
    sixk = client.coverage().by_source("sec_form6k")
    assert sixk is not None
    assert (sixk.first_row_at, sixk.last_row_at, sixk.rows_total) == (None, None, 0)
    assert sixk.stale is True


@respx.mock
def test_coverage_cold_cache_503_is_retried_after_retry_after(client: Client) -> None:
    busy = httpx.Response(
        503,
        json={
            "message": "Coverage is being computed.",
            "extra": {"reason": "coverage_unavailable", "retry_after_seconds": 0},
        },
        headers={"Retry-After": "0"},
    )
    route = respx.get(f"{BASE_URL}/api/coverage/").mock(
        side_effect=[busy, httpx.Response(200, json=load("coverage"))]
    )
    assert client.coverage().sources
    assert route.call_count == 2


@respx.mock
def test_coverage_503_exhausted_raises_server_error() -> None:
    respx.get(f"{BASE_URL}/api/coverage/").mock(
        return_value=httpx.Response(
            503,
            json={"message": "busy", "extra": {"reason": "coverage_unavailable"}},
            headers={"Retry-After": "0"},
        )
    )
    with (
        Client(api_key="ak_live_test", base_url=BASE_URL, max_retries=1) as client,
        pytest.raises(ServerError) as info,
    ):
        client.coverage()
    assert info.value.extra["reason"] == "coverage_unavailable"


@respx.mock
async def test_async_coverage() -> None:
    respx.get(f"{BASE_URL}/api/coverage/").mock(
        return_value=httpx.Response(200, json=load("coverage"))
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        cov = await client.coverage()
    assert [s.source for s in cov.sources] == SOURCES
