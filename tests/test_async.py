"""Async client coverage: endpoints, aiter, error mapping."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest
import respx

from alphai import AsyncClient, NewsCategory, NotFoundError

from .conftest import BASE_URL, load, page


@respx.mock
async def test_async_news_list(article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([article], "c2"))
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        result = await client.news.list(symbol="NVDA")
        assert result.has_more
        assert result.results[0].enrichment.category is NewsCategory.EARNINGS


@respx.mock
async def test_async_trending_and_get(article: dict) -> None:
    uid = "788e477c66f3849b"
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        return_value=httpx.Response(200, json=[article])
    )
    respx.get(f"{BASE_URL}/api/news/{uid}/").mock(return_value=httpx.Response(200, json=article))
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        assert len(await client.news.trending()) == 1
        assert (await client.news.get(uid)).uid == uid


@respx.mock
async def test_async_iter_drains(article: dict, insider_article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([article, insider_article], "c2")),
            httpx.Response(200, json=page([article], None)),
        ]
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        got = [a async for a in client.news.iter()]
        assert len(got) == 3


@respx.mock
async def test_async_iter_max_items(article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([article, article], "c2")),
            httpx.Response(200, json=page([article], None)),
        ]
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        got = [a async for a in client.news.iter(max_items=3)]
        assert len(got) == 3


@respx.mock
async def test_async_symbols() -> None:
    respx.get(f"{BASE_URL}/api/symbols/NVDA/insider-summary/").mock(
        return_value=httpx.Response(200, json=load("insider_summary"))
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        summ = await client.symbols.insider_summary("NVDA")
        assert summ.buy_value_usd == Decimal("1240000.00")


@respx.mock
async def test_async_error_mapping() -> None:
    respx.get(f"{BASE_URL}/api/symbols/ZZZZ/").mock(
        return_value=httpx.Response(404, json={"message": "Not found."})
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        with pytest.raises(NotFoundError):
            await client.symbols.get("ZZZZ")
