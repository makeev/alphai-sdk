"""Pure per-endpoint request builders and response parsers.

Shared by the sync and async clients so URL paths, query-param assembly, and
JSON→model parsing live in exactly one place. Nothing here does I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any

from .errors import InvalidResponseError
from .models import (
    NewsCategory,
    NewsPagination,
    RichNewsArticle,
    Symbol,
    TickerInsiderSummary,
    TickerSentimentSummary,
)

# --- URL paths -------------------------------------------------------------

NEWS = "/api/news/"
NEWS_TRENDING = "/api/news/trending/"
NEWS_INSIDER = "/api/news/insider/"

# Reject path-breaking characters fail-fast, so a malformed uid/ticker yields a
# clear client-side error instead of a confusing server 400/404 (and can't
# inject extra path segments or query into the request).
_UNSAFE_SEGMENT = re.compile(r"[/?#%\s]")


def _path_segment(value: str, name: str) -> str:
    if not value or _UNSAFE_SEGMENT.search(value):
        raise ValueError(f"Invalid {name}: {value!r}")
    return value


def news_detail_path(uid: str) -> str:
    return f"/api/news/{_path_segment(uid, 'uid')}/"


def news_related_path(uid: str) -> str:
    return f"/api/news/{_path_segment(uid, 'uid')}/related/"


SYMBOLS = "/api/symbols/"


def symbol_detail_path(ticker: str) -> str:
    return f"/api/symbols/{_path_segment(ticker, 'ticker')}/"


def symbol_sentiment_path(ticker: str) -> str:
    return f"/api/symbols/{_path_segment(ticker, 'ticker')}/sentiment-summary/"


def symbol_insider_path(ticker: str) -> str:
    return f"/api/symbols/{_path_segment(ticker, 'ticker')}/insider-summary/"


# --- param types & helpers -------------------------------------------------

CategoryArg = str | NewsCategory | Iterable[str | NewsCategory] | None


def _as_str_list(value: CategoryArg) -> list[str] | None:
    """Normalize a category arg (single / enum / iterable) to a list of strings."""
    if value is None:
        return None
    if isinstance(value, (str, NewsCategory)):
        items: Iterable[str | NewsCategory] = [value]
    else:
        items = value
    out = [v.value if isinstance(v, NewsCategory) else str(v) for v in items]
    return out or None


def build_news_list_params(
    *,
    symbol: str | None = None,
    category: CategoryArg = None,
    exclude_categories: CategoryArg = None,
    min_relevance: int | None = None,
    collapse_stories: bool = False,
    cursor: str | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "category": _as_str_list(category),
        "exclude_categories": _as_str_list(exclude_categories),
        "min_relevance": min_relevance,
        "collapse": "story" if collapse_stories else None,
        "cursor": cursor,
        "page_size": page_size,
    }


def build_news_insider_params(
    *,
    symbol: str | None = None,
    cursor: str | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    return {"symbol": symbol, "cursor": cursor, "page_size": page_size}


def build_symbols_list_params(
    *,
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, Any]:
    return {"limit": limit, "offset": offset}


# --- response parsers ------------------------------------------------------


def parse_news_page(data: Any) -> NewsPagination:
    return NewsPagination.model_validate(data)


def parse_article(data: Any) -> RichNewsArticle:
    return RichNewsArticle.model_validate(data)


def parse_article_list(data: Any) -> list[RichNewsArticle]:
    """Parse a bare array of articles (trending)."""
    if not isinstance(data, list):
        raise InvalidResponseError(f"Expected a JSON array, got {type(data).__name__}")
    return [RichNewsArticle.model_validate(item) for item in data]


def parse_related(data: Any) -> list[RichNewsArticle]:
    """Parse the ``{"results": [...]}`` envelope of the related endpoint."""
    results = data.get("results", []) if isinstance(data, dict) else []
    return [RichNewsArticle.model_validate(item) for item in results]


def parse_symbol(data: Any) -> Symbol:
    return Symbol.model_validate(data)


def parse_symbol_list(data: Any) -> list[Symbol]:
    if not isinstance(data, list):
        raise InvalidResponseError(f"Expected a JSON array, got {type(data).__name__}")
    return [Symbol.model_validate(item) for item in data]


def parse_sentiment_summary(data: Any) -> TickerSentimentSummary:
    return TickerSentimentSummary.model_validate(data)


def parse_insider_summary(data: Any) -> TickerInsiderSummary:
    return TickerInsiderSummary.model_validate(data)
