"""Query builders for Brief and Radar, shared by sync and async resources."""

from __future__ import annotations

import math
from collections.abc import Iterable
from typing import Any

from .models.radar import (
    RadarMarket,
    RadarOrder,
    RadarScope,
    RadarSentimentFilter,
    RadarSort,
    RadarWindow,
)

TickersArg = str | Iterable[str]


def ticker_csv(value: TickersArg, *, max_length: int, max_count: int | None = None) -> str:
    items = [value] if isinstance(value, str) else value
    symbols: dict[str, None] = {}
    for item in items:
        if not isinstance(item, str):
            raise ValueError("tickers must contain strings")
        for part in item.split(","):
            symbol = part.strip().upper()
            if not symbol or len(symbol) > max_length:
                raise ValueError(f"Each ticker must have 1-{max_length} characters")
            symbols[symbol] = None
    if not symbols or (max_count is not None and len(symbols) > max_count):
        raise ValueError(
            "tickers must contain 1-100 distinct symbols"
            if max_count
            else "tickers must not be empty; omit the filter to scan the market"
        )
    return ",".join(symbols)


def integer_range(name: str, value: int | None, low: int, high: int | None = None) -> None:
    if value is not None and (
        type(value) is not int or value < low or (high is not None and value > high)
    ):
        raise ValueError(
            f"{name} must be an integer >= {low}" + (f" and <= {high}" if high else "")
        )


def build_brief_params(
    *, tickers: TickersArg, hours: int | None = None, limit: int | None = None
) -> dict[str, Any]:
    integer_range("hours", hours, 1, 168)
    integer_range("limit", limit, 1, 20)
    return {
        "tickers": ticker_csv(tickers, max_length=20, max_count=100),
        "hours": hours,
        "limit": limit,
    }


def build_radar_params(
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
) -> dict[str, Any]:
    if ticker is not None and tickers is not None:
        raise ValueError("Use ticker or tickers, not both")
    if cursor and offset:
        raise ValueError("Use cursor or offset, not both")
    integer_range("limit", limit, 1, 100)
    integer_range("offset", offset, 0)
    if min_z is not None and (
        isinstance(min_z, bool) or not math.isfinite(min_z) or not 0 <= min_z <= 8
    ):
        raise ValueError("min_z must be a finite number between 0 and 8")
    for name, value, choices in (
        ("window", window, ("4h", "24h")),
        ("scope", scope, ("market", "watchlist")),
        ("market", market, ("all", "us_equity", "crypto", "international")),
        ("sort", sort, ("score", "stories", "model_stories", "sentiment", "sentiment_change")),
        ("order", order, ("asc", "desc")),
        ("sentiment", sentiment, ("all", "positive", "negative", "mixed")),
    ):
        if value is not None and value not in choices:
            raise ValueError(f"Invalid {name}: {value!r}")
    if ticker is not None:
        ticker = ticker.strip().upper()
        if not ticker or len(ticker) > 32:
            raise ValueError("ticker must have 1-32 characters")
    if search is not None:
        search = search.strip().upper()
        if len(search) > 32:
            raise ValueError("search must have at most 32 characters")
    symbols = None if tickers is None else ticker_csv(tickers, max_length=32)
    if symbols is not None and len(symbols) > 16384:
        raise ValueError("tickers must have at most 16384 characters")
    if cursor is not None and len(cursor) > 4096:
        raise ValueError("cursor must have at most 4096 characters")
    return {
        "window": window,
        "scope": scope,
        "market": market,
        "ticker": ticker,
        "tickers": symbols,
        "search": search,
        "sort": sort,
        "order": order,
        "sentiment": sentiment,
        "min_z": min_z,
        "limit": limit,
        "offset": offset,
        "cursor": cursor,
    }
