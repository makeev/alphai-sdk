"""Optional live drift checks for Brief and Radar (ALPHAI_API_KEY required)."""

import os

import pytest

from alphai import AsyncClient, Client, ConflictError

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not os.environ.get("ALPHAI_API_KEY"), reason="ALPHAI_API_KEY not set"),
]


def test_live_brief_and_pinned_radar() -> None:
    with Client(max_retries=0) as client:
        brief = client.news.brief(tickers=["NVDA", "BTC-USD", "SDK-UNKNOWN"], hours=168, limit=2)
        assert brief.unknown_tickers == ["SDK-UNKNOWN"]
        assert "NVDA" in brief.tickers
        assert len(brief.events) <= 2 and len(brief.filings) <= 2
        page = client.radar.snapshot(limit=2)
        assert page.freshness.mode == "live"
        assert page.freshness.effective_delay_seconds >= page.access.delay_seconds
        if page.next_cursor:
            second = client.radar.snapshot(limit=2, cursor=page.next_cursor)
            assert second.snapshot_id == page.snapshot_id
            assert second.as_of == page.as_of
            assert second.offset == 2
            with pytest.raises(ConflictError):
                client.radar.snapshot(limit=3, cursor=page.next_cursor)


async def test_live_async_brief_and_saved_watchlist() -> None:
    async with AsyncClient(max_retries=0) as client:
        brief = await client.news.brief(tickers=["NVDA", "AMD"])
        assert "NVDA" in brief.tickers
        page = await client.radar.snapshot(scope="watchlist", limit=2)
        assert page.access.scope == "watchlist"
        assert page.watchlist_coverage is not None
        assert page.access.watchlist_count is not None
        if page.access.watchlist_count == 0:
            assert not page.results
