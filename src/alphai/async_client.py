"""Asynchronous client for the AlphaAI REST API.

Mirrors :mod:`alphai.client` method-for-method, reusing the same request
builders, parsers, and core helpers; only the transport and sleeps are async.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import TracebackType
from typing import Any

import httpx

from . import _requests as rq
from ._config import (
    DEFAULT_BACKOFF_FACTOR,
    DEFAULT_BASE_URL,
    DEFAULT_MAX_RETRIES,
    DEFAULT_MAX_RETRY_AFTER,
    DEFAULT_TIMEOUT,
    USER_AGENT,
    ClientConfig,
    resolve_api_key,
)
from ._core import (
    RateLimit,
    build_headers,
    build_url,
    clean_params,
    compute_backoff,
    error_from_response,
    parse_json,
    parse_retry_after,
    should_retry,
)
from ._requests import CategoryArg, SortArg
from .errors import APIConnectionError, InvalidResponseError
from .models import (
    NewsPagination,
    RichNewsArticle,
    Symbol,
    TickerInsiderSummary,
    TickerSentimentSummary,
)
from .pagination import aiterate_pages

# Module-scope aliases so `-> list[...]` return types don't resolve to the
# `list` *method* defined on the resource classes below.
_ArticleList = list[RichNewsArticle]
_SymbolList = list[Symbol]


class AsyncClient:
    """An asynchronous AlphaAI API client.

    Use as an async context manager to close the connection pool::

        async with AsyncClient() as client:
            page = await client.news.list(symbol="NVDA")

    A custom ``http_client`` is supported (advanced); the SDK still applies its
    auth header and base URL on every request, so the key and host always take
    effect. ``max_retries`` is clamped to ``>= 0``.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        max_retry_after: float = DEFAULT_MAX_RETRY_AFTER,
        user_agent: str = USER_AGENT,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = ClientConfig(
            api_key=resolve_api_key(api_key),
            base_url=base_url,
            timeout=timeout,
            max_retries=max(0, max_retries),
            backoff_factor=backoff_factor,
            max_retry_after=max_retry_after,
            user_agent=user_agent,
        )
        if http_client is not None:
            self._http = http_client
            self._owns_http = False
        else:
            self._http = httpx.AsyncClient(timeout=timeout)
            self._owns_http = True

        self.last_rate_limit: RateLimit | None = None
        self.news = AsyncNewsResource(self)
        self.symbols = AsyncSymbolsResource(self)

    async def request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        """Issue a request with retries and return the parsed JSON body.

        Auth header and base URL are applied here, so they take effect even when
        a custom ``http_client`` was supplied.
        """
        cleaned = clean_params(params or {})
        url = build_url(self._config.base_url, path)
        headers = build_headers(self._config)
        backoff = self._config.backoff_factor
        max_retry_after = self._config.max_retry_after
        attempts = self._config.max_retries + 1
        for attempt in range(attempts):
            try:
                response = await self._http.request(method, url, params=cleaned, headers=headers)
            except httpx.HTTPError as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(compute_backoff(attempt, backoff))
                    continue
                raise APIConnectionError(str(exc), cause=exc) from exc

            rate = RateLimit.from_headers(response.headers)
            if rate is not None:
                self.last_rate_limit = rate

            if response.status_code < 400:
                data = parse_json(response)
                if data is None:
                    raise InvalidResponseError(
                        f"Expected a JSON body from {method} {path} "
                        f"(status {response.status_code}), got none"
                    )
                return data
            if should_retry(response.status_code) and attempt + 1 < attempts:
                retry_after = parse_retry_after(response.headers)
                await asyncio.sleep(compute_backoff(attempt, backoff, retry_after, max_retry_after))
                continue
            raise error_from_response(response)

        raise APIConnectionError("request did not complete")  # pragma: no cover

    async def close(self) -> None:
        """Close the underlying HTTP connection pool (if owned by this client)."""
        if self._owns_http:
            await self._http.aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.close()


class AsyncNewsResource:
    """Async news endpoints."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def list(
        self,
        *,
        symbol: str | None = None,
        category: CategoryArg = None,
        exclude_categories: CategoryArg = None,
        min_relevance: int | None = None,
        collapse_stories: bool = False,
        cursor: str | None = None,
        page_size: int | None = None,
        sort: SortArg = None,
    ) -> NewsPagination:
        """One page of the main feed. ``page_size`` is 1-20 on any key
        (default 10), 21-50 needs a Pro key.

        ``sort="ingested"`` switches to delta polling - see
        :meth:`alphai.client.NewsResource.list`."""
        params = rq.build_news_list_params(
            symbol=symbol,
            category=category,
            exclude_categories=exclude_categories,
            min_relevance=min_relevance,
            collapse_stories=collapse_stories,
            cursor=cursor,
            page_size=page_size,
            sort=sort,
        )
        return rq.parse_news_page(await self._client.request("GET", rq.NEWS, params), sort)

    def iter(
        self,
        *,
        symbol: str | None = None,
        category: CategoryArg = None,
        exclude_categories: CategoryArg = None,
        min_relevance: int | None = None,
        collapse_stories: bool = False,
        page_size: int | None = None,
        sort: SortArg = None,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> AsyncIterator[RichNewsArticle]:
        """Auto-paginate the main feed (``async for article in ...``).

        With ``sort="ingested"`` this drains what is currently new and stops
        once caught up; keep a long-lived poller by storing ``next_cursor``
        from :meth:`list` yourself."""

        async def fetch(cursor: str | None) -> NewsPagination:
            return await self.list(
                symbol=symbol,
                category=category,
                exclude_categories=exclude_categories,
                min_relevance=min_relevance,
                collapse_stories=collapse_stories,
                cursor=cursor,
                page_size=page_size,
                sort=sort,
            )

        return aiterate_pages(fetch, max_items=max_items, max_pages=max_pages)

    async def trending(self) -> _ArticleList:
        """Top ≤10 stories from the last 48h."""
        return rq.parse_article_list(await self._client.request("GET", rq.NEWS_TRENDING))

    async def insider(
        self,
        *,
        symbol: str | None = None,
        min_relevance: int | None = None,
        cursor: str | None = None,
        page_size: int | None = None,
        sort: SortArg = None,
    ) -> NewsPagination:
        """One page of the insider (SEC Form 4) feed. ``page_size`` is 1-20 on
        any key (default 10), 21-50 needs Pro. ``min_relevance`` (1-10)
        overrides the default relevance floor — insider rows score
        deterministically from the event's summed value, so this is the
        "only large trades" dial. Items carry a structured ``insider`` block
        (side / shares / avg price / value / who).

        ``sort="ingested"`` delta-polls this feed under the same contract as
        :meth:`list`, with its own cursor family."""
        params = rq.build_news_insider_params(
            symbol=symbol,
            min_relevance=min_relevance,
            cursor=cursor,
            page_size=page_size,
            sort=sort,
        )
        return rq.parse_news_page(await self._client.request("GET", rq.NEWS_INSIDER, params), sort)

    def insider_iter(
        self,
        *,
        symbol: str | None = None,
        min_relevance: int | None = None,
        page_size: int | None = None,
        sort: SortArg = None,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> AsyncIterator[RichNewsArticle]:
        """Auto-paginate the insider feed."""

        async def fetch(cursor: str | None) -> NewsPagination:
            return await self.insider(
                symbol=symbol,
                min_relevance=min_relevance,
                cursor=cursor,
                page_size=page_size,
                sort=sort,
            )

        return aiterate_pages(fetch, max_items=max_items, max_pages=max_pages)

    async def get(self, uid: str) -> RichNewsArticle:
        """Fetch a single article by its 16-char hex uid."""
        return rq.parse_article(await self._client.request("GET", rq.news_detail_path(uid)))

    async def related(self, uid: str) -> _ArticleList:
        """Up to 6 articles related to the given article."""
        return rq.parse_related(await self._client.request("GET", rq.news_related_path(uid)))


class AsyncSymbolsResource:
    """Async symbol endpoints."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def list(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> _SymbolList:
        """All active tickers (alphabetical); slice with limit/offset."""
        params = rq.build_symbols_list_params(limit=limit, offset=offset)
        return rq.parse_symbol_list(await self._client.request("GET", rq.SYMBOLS, params))

    async def get(self, ticker: str) -> Symbol:
        """Extended metadata for one ticker (404 if unknown)."""
        return rq.parse_symbol(await self._client.request("GET", rq.symbol_detail_path(ticker)))

    async def sentiment_summary(self, ticker: str) -> TickerSentimentSummary:
        """7-day AI sentiment rollup (zeros for a well-formed unknown ticker)."""
        data = await self._client.request("GET", rq.symbol_sentiment_path(ticker))
        return rq.parse_sentiment_summary(data)

    async def insider_summary(self, ticker: str) -> TickerInsiderSummary:
        """30-day insider-transaction rollup (zeros for an unknown ticker)."""
        data = await self._client.request("GET", rq.symbol_insider_path(ticker))
        return rq.parse_insider_summary(data)


__all__ = ["AsyncClient", "AsyncNewsResource", "AsyncSymbolsResource"]
