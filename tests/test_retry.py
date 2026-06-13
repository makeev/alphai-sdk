"""Retry behavior on 429 / 5xx / connection errors."""

from __future__ import annotations

import httpx
import pytest
import respx

from alphai import APIConnectionError, BadRequestError, Client, RateLimitError, ServerError

from .conftest import BASE_URL


def _client(max_retries: int = 2) -> Client:
    # backoff_factor=0 keeps retries instant in tests.
    return Client(
        api_key="ak_live_test",
        base_url=BASE_URL,
        max_retries=max_retries,
        backoff_factor=0.0,
    )


@respx.mock
def test_429_then_success_is_retried(article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=[
            httpx.Response(429, json={"message": "throttled"}, headers={"Retry-After": "0"}),
            httpx.Response(200, json=[article]),
        ]
    )
    client = _client()
    items = client.news.trending()
    assert len(items) == 1
    assert route.call_count == 2
    client.close()


@respx.mock
def test_500_then_success_is_retried(article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=[
            httpx.Response(503, json={"message": "unavailable"}),
            httpx.Response(200, json=[article]),
        ]
    )
    client = _client()
    assert len(client.news.trending()) == 1
    assert route.call_count == 2
    client.close()


@respx.mock
def test_retries_exhausted_raises() -> None:
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        return_value=httpx.Response(500, json={"message": "boom"})
    )
    client = _client(max_retries=2)
    with pytest.raises(ServerError):
        client.news.trending()
    client.close()


@respx.mock
def test_no_retry_when_disabled() -> None:
    route = respx.get(f"{BASE_URL}/api/news/trending/").mock(
        return_value=httpx.Response(
            429, json={"message": "throttled"}, headers={"Retry-After": "0"}
        )
    )
    client = _client(max_retries=0)
    with pytest.raises(RateLimitError):
        client.news.trending()
    assert route.call_count == 1
    client.close()


@respx.mock
def test_connection_error_retried_then_raises() -> None:
    route = respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=httpx.ConnectError("connection refused")
    )
    client = _client(max_retries=2)
    with pytest.raises(APIConnectionError):
        client.news.trending()
    assert route.call_count == 3  # initial + 2 retries
    client.close()


@respx.mock
def test_connection_error_then_success(article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=[httpx.ConnectError("reset"), httpx.Response(200, json=[article])]
    )
    client = _client(max_retries=2)
    assert len(client.news.trending()) == 1
    assert route.call_count == 2
    client.close()


@respx.mock
def test_4xx_not_retried(article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(400, json={"message": "bad"})
    )
    client = _client(max_retries=2)
    with pytest.raises(BadRequestError):
        client.news.list()
    assert route.call_count == 1  # 400 is not retryable
    client.close()
