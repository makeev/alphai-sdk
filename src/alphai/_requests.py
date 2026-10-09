"""Pure per-endpoint request builders and response parsers.

Shared by the sync and async clients so URL paths, query-param assembly, and
JSON→model parsing live in exactly one place. Nothing here does I/O.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import date, datetime
from typing import Any, Literal

import httpx

from .errors import InvalidResponseError
from .models import (
    Coverage,
    InsiderCsvExport,
    LatestEarningsPointer,
    NewsCategory,
    NewsPagination,
    NewsSearchPage,
    RichNewsArticle,
    Symbol,
    TickerEarningsHistory,
    TickerInsiderSummary,
    TickerSentimentSummary,
)

# --- URL paths -------------------------------------------------------------

NEWS = "/api/news/"
NEWS_SEARCH = "/api/news/search/"
NEWS_TRENDING = "/api/news/trending/"
NEWS_INSIDER = "/api/news/insider/"
COVERAGE = "/api/coverage/"

#: ``Accept`` for ``format=csv``. The API answers ``format=csv`` together with
#: an ``Accept: application/json`` (the SDK's default) with 406, so the CSV
#: request asks for CSV first; error bodies stay JSON either way.
CSV_ACCEPT = "text/csv, application/json;q=0.9"

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


def symbol_earnings_path(ticker: str) -> str:
    return f"/api/symbols/{_path_segment(ticker, 'ticker')}/earnings/"


def symbol_earnings_latest_path(ticker: str) -> str:
    return f"/api/symbols/{_path_segment(ticker, 'ticker')}/earnings/latest/"


# --- param types & helpers -------------------------------------------------

CategoryArg = str | NewsCategory | Iterable[str | NewsCategory] | None
SourceTypeArg = str | Iterable[str] | None

#: Feed ordering. ``published`` (the default) is the reverse-chronological feed
#: and pages into older history. ``ingested`` is delta polling: rows in the
#: order they became available, ascending, so a poller cannot miss a late
#: arrival. The two mint SEPARATE cursor families — replaying a cursor into the
#: other mode is a 400, so pass the same ``sort`` on every call of a run.
SortArg = Literal["published", "ingested"] | None

#: A publication-window bound (``from_date`` / ``to_date``). A ``date`` (or a
#: bare ``YYYY-MM-DD`` string) means the WHOLE day — the server reads a bare
#: ``to_date`` as that day's end, so ``from_date=to_date=<day>`` returns the
#: day rather than an empty page. A ``datetime`` is the exact instant (naive is
#: read as UTC). Strings pass through untouched, so any server-accepted ISO
#: form works verbatim.
DateArg = str | date | datetime | None


def _as_date_param(value: DateArg) -> str | None:
    """Serialize a window bound, keeping the bare-date form bare.

    ``isoformat()`` does the right thing for both types: ``date`` yields
    ``YYYY-MM-DD`` (the whole-day form) and ``datetime`` yields the exact
    instant, offset included when the value is aware.
    """
    if value is None or isinstance(value, str):
        return value
    return value.isoformat()


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
    sort: SortArg = None,
    from_date: DateArg = None,
    to_date: DateArg = None,
    source_type: SourceTypeArg = None,
    item: str | None = None,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "category": _as_str_list(category),
        "exclude_categories": _as_str_list(exclude_categories),
        "min_relevance": min_relevance,
        "collapse": "story" if collapse_stories else None,
        "cursor": cursor,
        "page_size": page_size,
        "sort": sort,
        "from_date": _as_date_param(from_date),
        "to_date": _as_date_param(to_date),
        "source_type": _as_str_list(source_type),
        "item": item,
    }


def build_news_search_params(
    query: str,
    *,
    symbol: str | None = None,
    category: CategoryArg = None,
    source_type: SourceTypeArg = None,
    item: str | None = None,
    min_relevance: int | None = None,
    collapse_stories: bool = False,
    cursor: str | None = None,
    page_size: int | None = None,
    from_date: DateArg = None,
    to_date: DateArg = None,
) -> dict[str, Any]:
    return {
        "q": query,
        "symbol": symbol,
        "category": _as_str_list(category),
        "source_type": _as_str_list(source_type),
        "item": item,
        "min_relevance": min_relevance,
        "collapse": "story" if collapse_stories else None,
        "cursor": cursor,
        "page_size": page_size,
        "from_date": _as_date_param(from_date),
        "to_date": _as_date_param(to_date),
    }


def build_news_insider_params(
    *,
    symbol: str | None = None,
    min_relevance: int | None = None,
    cursor: str | None = None,
    page_size: int | None = None,
    sort: SortArg = None,
    from_date: DateArg = None,
    to_date: DateArg = None,
    is_10b5_1: bool | None = None,
) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "min_relevance": min_relevance,
        "is_10b5_1": is_10b5_1,
        "cursor": cursor,
        "page_size": page_size,
        "sort": sort,
        "from_date": _as_date_param(from_date),
        "to_date": _as_date_param(to_date),
    }


def build_news_insider_csv_params(
    *,
    symbol: str | None = None,
    min_relevance: int | None = None,
    cursor: str | None = None,
    sort: SortArg = None,
    from_date: DateArg = None,
    to_date: DateArg = None,
    is_10b5_1: bool | None = None,
) -> dict[str, Any]:
    """The insider feed's filters plus ``format=csv``; ``page_size`` has no
    effect on an export, so it is not offered."""
    params = build_news_insider_params(
        symbol=symbol,
        min_relevance=min_relevance,
        cursor=cursor,
        sort=sort,
        from_date=from_date,
        to_date=to_date,
        is_10b5_1=is_10b5_1,
    )
    params["format"] = "csv"
    return params


def build_symbols_list_params(
    *,
    limit: int | None = None,
    offset: int | None = None,
    search: str | None = None,
) -> dict[str, Any]:
    return {"limit": limit, "offset": offset, "search": search}


# --- response parsers ------------------------------------------------------


def parse_news_page(data: Any, sort: SortArg = None) -> NewsPagination:
    """Parse a feed page, stamping it with the sort mode that produced it.

    The mode is not in the response body, but ``has_more`` / ``caught_up``
    resolve differently per mode — so the request layer, which is the only
    place that knows what was asked for, hands it to the model.
    """
    page = NewsPagination.model_validate(data)
    page._sort = sort or "published"
    return page


def parse_news_search_page(data: Any) -> NewsSearchPage:
    return NewsSearchPage.model_validate(data)


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


def parse_earnings(data: Any) -> TickerEarningsHistory:
    return TickerEarningsHistory.model_validate(data)


def parse_latest_earnings(data: Any) -> LatestEarningsPointer | None:
    """``None`` when the API answered 204: no read has been published for the ticker yet."""
    if data is None:
        return None
    return LatestEarningsPointer.model_validate(data)


def parse_coverage(data: Any) -> Coverage:
    return Coverage.model_validate(data)


_FILENAME = re.compile(r'filename="?([^";]+)"?')


def _header_int(headers: httpx.Headers, name: str) -> int | None:
    try:
        return int(headers[name])
    except (KeyError, ValueError):
        return None


def parse_insider_csv(response: httpx.Response) -> InsiderCsvExport:
    """Read a ``format=csv`` response: the file body plus its ``X-Alphai-*`` headers.

    ``X-Alphai-Truncated: false`` (the file holds everything the filters
    select) becomes ``truncated=None``, so ``if export.truncated:`` reads true
    only when there is more to fetch or the archive horizon stopped the walk.
    """
    content_type = response.headers.get("content-type", "")
    if not content_type.startswith("text/csv"):
        raise InvalidResponseError(
            f"Expected a text/csv body from the insider export, got {content_type or 'none'!r}"
        )
    headers = response.headers
    truncated = headers.get("x-alphai-truncated")
    match = _FILENAME.search(headers.get("content-disposition", ""))
    return InsiderCsvExport(
        text=response.text,
        rows=_header_int(headers, "x-alphai-rows"),
        row_cap=_header_int(headers, "x-alphai-row-cap"),
        truncated=None if truncated in (None, "", "false") else truncated,
        next_cursor=headers.get("x-alphai-next-cursor") or None,
        filename=match.group(1) if match else None,
    )
