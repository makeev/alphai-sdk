"""Client construction, API-key resolution, rate-limit capture."""

from __future__ import annotations

import httpx
import pytest
import respx

from alphai import Client, MissingAPIKeyError
from alphai._config import DEFAULT_BASE_URL, resolve_api_key

from .conftest import BASE_URL, page


def test_resolve_api_key_explicit() -> None:
    assert resolve_api_key("ak_live_explicit") == "ak_live_explicit"


def test_resolve_api_key_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ALPHAI_API_KEY", "ak_live_from_env")
    assert resolve_api_key(None) == "ak_live_from_env"


def test_resolve_api_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ALPHAI_API_KEY", raising=False)
    with pytest.raises(MissingAPIKeyError):
        resolve_api_key(None)


def test_default_base_url() -> None:
    assert DEFAULT_BASE_URL == "https://api.alphai.io"


def test_last_rate_limit_starts_none() -> None:
    client = Client(api_key="ak_live_test")
    assert client.last_rate_limit is None
    client.close()


@respx.mock
def test_rate_limit_captured_after_call(client: Client, article: dict) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(
            200,
            json=page([article], None),
            headers={
                "X-RateLimit-Limit": "1000",
                "X-RateLimit-Remaining": "997",
                "X-RateLimit-Reset": "1718380800",
            },
        )
    )
    client.news.list()
    assert client.last_rate_limit is not None
    assert client.last_rate_limit.limit == 1000
    assert client.last_rate_limit.remaining == 997
    assert client.last_rate_limit.reset == 1718380800


def test_context_manager_closes() -> None:
    with Client(api_key="ak_live_test") as client:
        assert isinstance(client, Client)
    # double close is safe
    client.close()
