"""Retry behavior on 429 / 5xx / connection errors."""

from __future__ import annotations

import logging

import httpx
import pytest
import respx

from alphai import (
    APIConnectionError,
    AsyncClient,
    BadRequestError,
    Client,
    RateLimitError,
    ServerError,
)

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


# --- the wait before a retry is logged (a sleeping client must not look hung) ---


@respx.mock
def test_429_wait_is_logged_with_retry_after_and_daily_budget(
    article: dict, caplog: pytest.LogCaptureFixture
) -> None:
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=[
            httpx.Response(
                429,
                json={"message": "throttled"},
                headers={
                    "Retry-After": "0",
                    "X-RateLimit-Limit": "100",
                    "X-RateLimit-Remaining": "87",
                    "X-RateLimit-Reset": "1791590400",
                },
            ),
            httpx.Response(200, json=[article]),
        ]
    )
    client = _client()
    with caplog.at_level(logging.WARNING, logger="alphai"):
        client.news.trending()
    client.close()
    [record] = [r for r in caplog.records if r.name == "alphai"]
    assert record.levelno == logging.WARNING
    message = record.getMessage()
    assert "HTTP 429 (rate limited) on GET /api/news/trending/" in message
    assert "waiting 0.0s before retry 1 of 2" in message
    assert "Retry-After: 0s" in message
    assert "daily budget 87/100 left" in message


@respx.mock
def test_each_retry_wait_is_logged_and_success_logs_nothing_more(
    article: dict, caplog: pytest.LogCaptureFixture
) -> None:
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=[
            httpx.Response(503, json={"message": "unavailable"}),
            httpx.ConnectError("reset"),
            httpx.Response(200, json=[article]),
        ]
    )
    client = _client()
    with caplog.at_level(logging.WARNING, logger="alphai"):
        client.news.trending()
    client.close()
    messages = [r.getMessage() for r in caplog.records if r.name == "alphai"]
    assert len(messages) == 2
    assert "HTTP 503 (server error)" in messages[0]
    assert "retry 1 of 2" in messages[0]
    assert "daily budget" not in messages[0]
    assert "connection error (ConnectError)" in messages[1]
    assert "retry 2 of 2" in messages[1]


@respx.mock
def test_final_failure_and_clean_calls_are_not_logged(
    article: dict, caplog: pytest.LogCaptureFixture
) -> None:
    throttled = httpx.Response(429, json={"message": "throttled"}, headers={"Retry-After": "0"})
    respx.get(f"{BASE_URL}/api/news/trending/").mock(return_value=throttled)
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json={"results": [article], "next_cursor": None})
    )
    client = _client(max_retries=0)
    with caplog.at_level(logging.DEBUG, logger="alphai"):
        client.news.list()
        with pytest.raises(RateLimitError):
            client.news.trending()  # no retry left: raised, never slept on
    client.close()
    assert [r for r in caplog.records if r.name == "alphai"] == []


@respx.mock
def test_logged_wait_is_the_capped_retry_after(
    article: dict, caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    slept: list[float] = []
    monkeypatch.setattr("alphai.client.time.sleep", slept.append)
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=[
            httpx.Response(429, json={"message": "day cap"}, headers={"Retry-After": "3600"}),
            httpx.Response(200, json=[article]),
        ]
    )
    client = Client(api_key="ak_live_test", base_url=BASE_URL, max_retry_after=7)
    with caplog.at_level(logging.WARNING, logger="alphai"):
        client.news.trending()
    client.close()
    assert slept == [7.0]
    [record] = [r for r in caplog.records if r.name == "alphai"]
    assert "waiting 7.0s" in record.getMessage()
    assert "Retry-After: 3600s" in record.getMessage()


@respx.mock
async def test_async_429_wait_is_logged(article: dict, caplog: pytest.LogCaptureFixture) -> None:
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=[
            httpx.Response(429, json={"message": "throttled"}, headers={"Retry-After": "0"}),
            httpx.Response(200, json=[article]),
        ]
    )
    with caplog.at_level(logging.WARNING, logger="alphai"):
        async with AsyncClient(
            api_key="ak_live_test", base_url=BASE_URL, backoff_factor=0.0
        ) as client:
            assert len(await client.news.trending()) == 1
    [record] = [r for r in caplog.records if r.name == "alphai"]
    assert "HTTP 429 (rate limited) on GET /api/news/trending/" in record.getMessage()
