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
    DEFAULT_TIMEOUT,
    ClientConfig,
    resolve_api_key,
)
from ._core import (
    RateLimit,
    build_headers,
    clean_params,
    compute_backoff,
    error_from_response,
    parse_json,
    parse_retry_after,
    should_retry,
)
from ._requests import CategoryArg
from .errors import APIConnectionError
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
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_factor: float = DEFAULT_BACKOFF_FACTOR,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._config = ClientConfig(
            api_key=resolve_api_key(api_key),
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )
        if http_client is not None:
            self._http = http_client
            self._owns_http = False
        else:
            self._http = httpx.AsyncClient(
                base_url=base_url,
                timeout=timeout,
                headers=build_headers(self._config),
            )
            self._owns_http = True

        self.last_rate_limit: RateLimit | None = None
        self.news = AsyncNewsResource(self)
        self.symbols = AsyncSymbolsResource(self)

    async def request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        """Issue a request with retries and return the parsed JSON body."""
        cleaned = clean_params(params or {})
        attempts = self._config.max_retries + 1
        for attempt in range(attempts):
            try:
                response = await self._http.request(method, path, params=cleaned)
            except httpx.HTTPError as exc:
                if attempt + 1 < attempts:
                    await asyncio.sleep(compute_backoff(attempt, self._config.backoff_factor))
                    continue
                raise APIConnectionError(str(exc), cause=exc) from exc

            rate = RateLimit.from_headers(response.headers)
            if rate is not None:
                self.last_rate_limit = rate

            if response.status_code < 400:
                return parse_json(response)
            if should_retry(response.status_code) and attempt + 1 < attempts:
                retry_after = parse_retry_after(response.headers)
                await asyncio.sleep(
                    compute_backoff(attempt, self._config.backoff_factor, retry_after)
                )
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
    ) -> NewsPagination:
        """One page of the main feed (newest first)."""
        params = rq.build_news_list_params(
            symbol=symbol,
            category=category,
            exclude_categories=exclude_categories,
            min_relevance=min_relevance,
            collapse_stories=collapse_stories,
            cursor=cursor,
        )
        return rq.parse_news_page(await self._client.request("GET", rq.NEWS, params))

    def iter(
        self,
        *,
        symbol: str | None = None,
        category: CategoryArg = None,
        exclude_categories: CategoryArg = None,
        min_relevance: int | None = None,
        collapse_stories: bool = False,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> AsyncIterator[RichNewsArticle]:
        """Auto-paginate the main feed (``async for article in ...``)."""

        async def fetch(cursor: str | None) -> NewsPagination:
            return await self.list(
                symbol=symbol,
                category=category,
                exclude_categories=exclude_categories,
                min_relevance=min_relevance,
                collapse_stories=collapse_stories,
                cursor=cursor,
            )

        return aiterate_pages(fetch, max_items=max_items, max_pages=max_pages)

    async def trending(self) -> _ArticleList:
        """Top ≤10 stories from the last 48h."""
        return rq.parse_article_list(await self._client.request("GET", rq.NEWS_TRENDING))

    async def insider(
        self,
        *,
        symbol: str | None = None,
        cursor: str | None = None,
    ) -> NewsPagination:
        """One page of the insider (SEC Form 4) feed."""
        params = rq.build_news_insider_params(symbol=symbol, cursor=cursor)
        return rq.parse_news_page(await self._client.request("GET", rq.NEWS_INSIDER, params))

    def insider_iter(
        self,
        *,
        symbol: str | None = None,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> AsyncIterator[RichNewsArticle]:
        """Auto-paginate the insider feed."""

        async def fetch(cursor: str | None) -> NewsPagination:
            return await self.insider(symbol=symbol, cursor=cursor)

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
