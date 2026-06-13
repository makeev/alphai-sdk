"""Error envelope parsing and status -> exception mapping."""

from __future__ import annotations

import httpx
import pytest
import respx

from alphai import (
    AuthenticationError,
    BadRequestError,
    Client,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)

from .conftest import BASE_URL


@respx.mock
def test_401_detail_shape(client: Client) -> None:
    # Host-gate middleware returns {"detail": ...} before DRF.
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(401, json={"detail": "API key required."})
    )
    with pytest.raises(AuthenticationError) as exc:
        client.news.list()
    assert exc.value.message == "API key required."
    assert exc.value.status == 401


@respx.mock
def test_401_message_shape(client: Client) -> None:
    # DRF custom handler returns {"message": ..., "extra": {}}.
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(
            401, json={"message": "Invalid or revoked API key.", "extra": {}}
        )
    )
    with pytest.raises(AuthenticationError) as exc:
        client.news.list()
    assert exc.value.message == "Invalid or revoked API key."


@respx.mock
def test_400_validation_fields(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(
            400,
            json={
                "message": "Validation error",
                "extra": {"fields": {"min_relevance": ["too big"]}},
            },
        )
    )
    with pytest.raises(BadRequestError) as exc:
        client.news.list(min_relevance=99)
    assert exc.value.fields == {"min_relevance": ["too big"]}


@respx.mock
def test_403(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(403, json={"message": "Insufficient permissions."})
    )
    with pytest.raises(PermissionDeniedError):
        client.news.list()


@respx.mock
def test_404(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/symbols/ZZZZ/").mock(
        return_value=httpx.Response(404, json={"message": "Not found."})
    )
    with pytest.raises(NotFoundError):
        client.symbols.get("ZZZZ")


@respx.mock
def test_429_carries_rate_limit_details() -> None:
    client = Client(api_key="ak_live_test", base_url=BASE_URL, max_retries=0)
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(
            429,
            json={"message": "Request was throttled."},
            headers={
                "Retry-After": "45",
                "X-RateLimit-Limit": "100",
                "X-RateLimit-Remaining": "0",
                "X-RateLimit-Reset": "1718380800",
            },
        )
    )
    with pytest.raises(RateLimitError) as exc:
        client.news.list()
    assert exc.value.retry_after == 45
    assert exc.value.limit == 100
    assert exc.value.remaining == 0
    assert exc.value.reset == 1718380800
    client.close()


@respx.mock
def test_500() -> None:
    client = Client(api_key="ak_live_test", base_url=BASE_URL, max_retries=0)
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(500, json={"message": "Internal server error."})
    )
    with pytest.raises(ServerError):
        client.news.list()
    client.close()


@respx.mock
def test_non_json_error_body(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(404, text="<html>not found</html>")
    )
    with pytest.raises(NotFoundError) as exc:
        client.news.list()
    assert "not found" in exc.value.message
