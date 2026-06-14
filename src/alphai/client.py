"""Synchronous client for the AlphaAI REST API."""

from __future__ import annotations

import time
from collections.abc import Iterator
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
from ._requests import CategoryArg
from .errors import APIConnectionError, InvalidResponseError
from .models import (
    NewsPagination,
    RichNewsArticle,
    Symbol,
    TickerInsiderSummary,
    TickerSentimentSummary,
)
from .pagination import iterate_pages

# Module-scope aliases so `-> list[...]` return types don't resolve to the
# `list` *method* defined on the resource classes below.
_ArticleList = list[RichNewsArticle]
_SymbolList = list[Symbol]


class Client:
    """A synchronous AlphaAI API client.

    Args:
        api_key: Your ``ak_live_…`` key. Falls back to ``$ALPHAI_API_KEY``.
        base_url: API host. Defaults to ``https://api.alphai.io``.
        timeout: Per-request timeout in seconds.
        max_retries: Retries on 429 / 5xx / connection errors (idempotent GETs).
            Negative values are clamped to 0.
        backoff_factor: Base for the jittered exponential backoff.
        max_retry_after: Cap (seconds) on how long a server ``Retry-After`` is
            honored, so a bad value can't freeze the caller.
        user_agent: Override the ``User-Agent`` header.
        http_client: Optional pre-configured ``httpx.Client`` (advanced). The SDK
            still applies its auth header and base URL on every request, so the
            key and host always take effect; you own the client's lifecycle,
            transport, proxies, and timeout.

    Use as a context manager to close the underlying connection pool::

        with Client() as client:
            page = client.news.list(symbol="NVDA")
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
        http_client: httpx.Client | None = None,
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
            self._http = httpx.Client(timeout=timeout)
            self._owns_http = True

        self.last_rate_limit: RateLimit | None = None
        self.news = NewsResource(self)
        self.symbols = SymbolsResource(self)

    def request(self, method: str, path: str, params: dict[str, Any] | None = None) -> Any:
        """Issue a request with retries and return the parsed JSON body.

        Mostly used internally by the resources; exposed for advanced callers.
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
                response = self._http.request(method, url, params=cleaned, headers=headers)
            except httpx.HTTPError as exc:
                if attempt + 1 < attempts:
                    time.sleep(compute_backoff(attempt, backoff))
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
                time.sleep(compute_backoff(attempt, backoff, retry_after, max_retry_after))
                continue
            raise error_from_response(response)

        raise APIConnectionError("request did not complete")  # pragma: no cover

    def close(self) -> None:
        """Close the underlying HTTP connection pool (if owned by this client)."""
        if self._owns_http:
            self._http.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        self.close()


class NewsResource:
    """News endpoints: feed, trending, insider, single article, related."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(
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
        return rq.parse_news_page(self._client.request("GET", rq.NEWS, params))

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
    ) -> Iterator[RichNewsArticle]:
        """Auto-paginate the main feed, yielding articles across pages."""

        def fetch(cursor: str | None) -> NewsPagination:
            return self.list(
                symbol=symbol,
                category=category,
                exclude_categories=exclude_categories,
                min_relevance=min_relevance,
                collapse_stories=collapse_stories,
                cursor=cursor,
            )

        return iterate_pages(fetch, max_items=max_items, max_pages=max_pages)

    def trending(self) -> _ArticleList:
        """Top ≤10 stories from the last 48h (no pagination)."""
        return rq.parse_article_list(self._client.request("GET", rq.NEWS_TRENDING))

    def insider(
        self,
        *,
        symbol: str | None = None,
        cursor: str | None = None,
    ) -> NewsPagination:
        """One page of the insider (SEC Form 4) feed."""
        params = rq.build_news_insider_params(symbol=symbol, cursor=cursor)
        return rq.parse_news_page(self._client.request("GET", rq.NEWS_INSIDER, params))

    def insider_iter(
        self,
        *,
        symbol: str | None = None,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> Iterator[RichNewsArticle]:
        """Auto-paginate the insider feed."""

        def fetch(cursor: str | None) -> NewsPagination:
            return self.insider(symbol=symbol, cursor=cursor)

        return iterate_pages(fetch, max_items=max_items, max_pages=max_pages)

    def get(self, uid: str) -> RichNewsArticle:
        """Fetch a single article by its 16-char hex uid."""
        return rq.parse_article(self._client.request("GET", rq.news_detail_path(uid)))

    def related(self, uid: str) -> _ArticleList:
        """Up to 6 articles related to the given article."""
        return rq.parse_related(self._client.request("GET", rq.news_related_path(uid)))


class SymbolsResource:
    """Symbol endpoints: listing, detail, sentiment / insider rollups."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def list(
        self,
        *,
        limit: int | None = None,
        offset: int | None = None,
    ) -> _SymbolList:
        """All active tickers (alphabetical); slice with limit/offset."""
        params = rq.build_symbols_list_params(limit=limit, offset=offset)
        return rq.parse_symbol_list(self._client.request("GET", rq.SYMBOLS, params))

    def get(self, ticker: str) -> Symbol:
        """Extended metadata for one ticker (404 if unknown)."""
        return rq.parse_symbol(self._client.request("GET", rq.symbol_detail_path(ticker)))

    def sentiment_summary(self, ticker: str) -> TickerSentimentSummary:
        """7-day AI sentiment rollup (zeros for a well-formed unknown ticker)."""
        data = self._client.request("GET", rq.symbol_sentiment_path(ticker))
        return rq.parse_sentiment_summary(data)

    def insider_summary(self, ticker: str) -> TickerInsiderSummary:
        """30-day insider-transaction rollup (zeros for an unknown ticker)."""
        data = self._client.request("GET", rq.symbol_insider_path(ticker))
        return rq.parse_insider_summary(data)


__all__ = ["Client", "NewsResource", "SymbolsResource"]
