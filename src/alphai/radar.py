"""Radar snapshots and iteration. A run never silently switches snapshots."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING

from ._snapshot_params import TickersArg, build_radar_params, integer_range
from .errors import InvalidResponseError
from .models.radar import (
    RadarMarket,
    RadarOrder,
    RadarReading,
    RadarScope,
    RadarSentimentFilter,
    RadarSnapshot,
    RadarSort,
    RadarWindow,
)

if TYPE_CHECKING:
    from .async_client import AsyncClient
    from .client import Client

RADAR = "/api/signals/snapshot/"


class RadarResource:
    """Rank market news or the caller's saved watchlist, with server-side tier delays."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def snapshot(
        self,
        *,
        window: RadarWindow | None = None,
        scope: RadarScope | None = None,
        market: RadarMarket | None = None,
        ticker: str | None = None,
        tickers: TickersArg | None = None,
        search: str | None = None,
        sort: RadarSort | None = None,
        order: RadarOrder | None = None,
        sentiment: RadarSentimentFilter | None = None,
        min_z: float | None = None,
        limit: int | None = None,
        offset: int | None = None,
        cursor: str | None = None,
    ) -> RadarSnapshot:
        """Return one snapshot page. Keep filters/limit unchanged when passing its cursor.

        Free/Basic/Pro delay the entire snapshot by 60/15/0 minutes. Inspect
        as_of/freshness; nullable metrics remain None. HTTP 409 raises
        ConflictError: restart a new scan without a cursor. HTTP 503 is unavailable
        data, not an empty result. scope='watchlist' reads the key owner's saved list.
        """
        params = build_radar_params(
            window=window,
            scope=scope,
            market=market,
            ticker=ticker,
            tickers=tickers,
            search=search,
            sort=sort,
            order=order,
            sentiment=sentiment,
            min_z=min_z,
            limit=limit,
            offset=offset,
            cursor=cursor,
        )
        return RadarSnapshot.model_validate(self._client.request("GET", RADAR, params))

    def iter(
        self,
        *,
        window: RadarWindow | None = None,
        scope: RadarScope | None = None,
        market: RadarMarket | None = None,
        ticker: str | None = None,
        tickers: TickersArg | None = None,
        search: str | None = None,
        sort: RadarSort | None = None,
        order: RadarOrder | None = None,
        sentiment: RadarSentimentFilter | None = None,
        min_z: float | None = None,
        limit: int | None = None,
        offset: int | None = None,
        cursor: str | None = None,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> Iterator[RadarReading]:
        """Iterate one pinned snapshot. Errors propagate; the scan never auto-restarts.

        Filters (including an iterable of tickers) are captured once. Offset is
        used only for the initial page, then the server's opaque cursor is followed.
        """
        integer_range("max_items", max_items, 0)
        integer_range("max_pages", max_pages, 0)
        params = build_radar_params(
            window=window,
            scope=scope,
            market=market,
            ticker=ticker,
            tickers=tickers,
            search=search,
            sort=sort,
            order=order,
            sentiment=sentiment,
            min_z=min_z,
            limit=limit,
            offset=offset,
            cursor=cursor,
        )
        count = pages = 0
        snapshot_id: str | None = None
        seen_cursors = {cursor} if cursor else set()
        while (max_items is None or count < max_items) and (max_pages is None or pages < max_pages):
            page = RadarSnapshot.model_validate(self._client.request("GET", RADAR, params))
            if snapshot_id is not None and page.snapshot_id != snapshot_id:
                raise InvalidResponseError("Radar snapshot changed during cursor pagination")
            snapshot_id = page.snapshot_id
            pages += 1
            for item in page.results:
                yield item
                count += 1
                if max_items is not None and count >= max_items:
                    return
            if not page.next_cursor:
                return
            if page.next_cursor in seen_cursors:
                raise InvalidResponseError("Radar repeated a pagination cursor")
            seen_cursors.add(page.next_cursor)
            params["cursor"] = page.next_cursor
            params["offset"] = None


class AsyncRadarResource:
    """Rank market news or the caller's saved watchlist, with server-side tier delays."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def snapshot(
        self,
        *,
        window: RadarWindow | None = None,
        scope: RadarScope | None = None,
        market: RadarMarket | None = None,
        ticker: str | None = None,
        tickers: TickersArg | None = None,
        search: str | None = None,
        sort: RadarSort | None = None,
        order: RadarOrder | None = None,
        sentiment: RadarSentimentFilter | None = None,
        min_z: float | None = None,
        limit: int | None = None,
        offset: int | None = None,
        cursor: str | None = None,
    ) -> RadarSnapshot:
        """Return one snapshot page. Keep filters/limit unchanged when passing its cursor.

        Free/Basic/Pro delay the entire snapshot by 60/15/0 minutes. Inspect
        as_of/freshness; nullable metrics remain None. HTTP 409 raises
        ConflictError: restart a new scan without a cursor. HTTP 503 is unavailable
        data, not an empty result. scope='watchlist' reads the key owner's saved list.
        """
        params = build_radar_params(
            window=window,
            scope=scope,
            market=market,
            ticker=ticker,
            tickers=tickers,
            search=search,
            sort=sort,
            order=order,
            sentiment=sentiment,
            min_z=min_z,
            limit=limit,
            offset=offset,
            cursor=cursor,
        )
        return RadarSnapshot.model_validate(await self._client.request("GET", RADAR, params))

    async def iter(
        self,
        *,
        window: RadarWindow | None = None,
        scope: RadarScope | None = None,
        market: RadarMarket | None = None,
        ticker: str | None = None,
        tickers: TickersArg | None = None,
        search: str | None = None,
        sort: RadarSort | None = None,
        order: RadarOrder | None = None,
        sentiment: RadarSentimentFilter | None = None,
        min_z: float | None = None,
        limit: int | None = None,
        offset: int | None = None,
        cursor: str | None = None,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> AsyncIterator[RadarReading]:
        """Iterate one pinned snapshot. Errors propagate; the scan never auto-restarts.

        Filters (including an iterable of tickers) are captured once. Offset is
        used only for the initial page, then the server's opaque cursor is followed.
        """
        integer_range("max_items", max_items, 0)
        integer_range("max_pages", max_pages, 0)
        params = build_radar_params(
            window=window,
            scope=scope,
            market=market,
            ticker=ticker,
            tickers=tickers,
            search=search,
            sort=sort,
            order=order,
            sentiment=sentiment,
            min_z=min_z,
            limit=limit,
            offset=offset,
            cursor=cursor,
        )
        count = pages = 0
        snapshot_id: str | None = None
        seen_cursors = {cursor} if cursor else set()
        while (max_items is None or count < max_items) and (max_pages is None or pages < max_pages):
            page = RadarSnapshot.model_validate(await self._client.request("GET", RADAR, params))
            if snapshot_id is not None and page.snapshot_id != snapshot_id:
                raise InvalidResponseError("Radar snapshot changed during cursor pagination")
            snapshot_id = page.snapshot_id
            pages += 1
            for item in page.results:
                yield item
                count += 1
                if max_items is not None and count >= max_items:
                    return
            if not page.next_cursor:
                return
            if page.next_cursor in seen_cursors:
                raise InvalidResponseError("Radar repeated a pagination cursor")
            seen_cursors.add(page.next_cursor)
            params["cursor"] = page.next_cursor
            params["offset"] = None
