"""Tests for the post-review hardening fixes (M1, M2, L1-L6, N1)."""

from __future__ import annotations

import httpx
import pytest
import respx

from alphai import Client, InvalidResponseError, NewsPagination
from alphai._config import ClientConfig
from alphai._core import build_url, compute_backoff

from .conftest import BASE_URL, page

# --- M1: Retry-After is capped --------------------------------------------


def test_compute_backoff_caps_retry_after() -> None:
    assert compute_backoff(0, 0.5, retry_after=3600, max_retry_after=60.0) == 60.0
    # under the cap, honored verbatim
    assert compute_backoff(0, 0.5, retry_after=5, max_retry_after=60.0) == 5.0
    # no cap -> verbatim (back-compat)
    assert compute_backoff(0, 0.5, retry_after=3600) == 3600.0


@respx.mock
def test_client_default_caps_retry_after(monkeypatch: pytest.MonkeyPatch) -> None:
    slept: list[float] = []
    monkeypatch.setattr("alphai.client.time.sleep", lambda s: slept.append(s))
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        side_effect=[
            httpx.Response(429, json={"message": "x"}, headers={"Retry-After": "9999"}),
            httpx.Response(200, json=[]),
        ]
    )
    client = Client(api_key="ak_live_test", max_retry_after=60.0)
    client.news.trending()
    assert slept == [60.0]  # 9999 capped to 60
    client.close()


# --- M2: custom http_client still gets auth + base URL ---------------------


@respx.mock
def test_custom_http_client_still_authenticates(article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([article], None))
    )
    # A bare client with no base_url and no headers — the SDK must still apply both.
    custom = httpx.Client()
    client = Client(api_key="ak_live_secret", http_client=custom)
    result = client.news.list(symbol="NVDA")
    assert result.results[0].uid == "788e477c66f3849b"
    sent = route.calls[0].request
    assert sent.headers["authorization"] == "Bearer ak_live_secret"
    assert str(sent.url).startswith(BASE_URL)
    custom.close()


def test_sdk_does_not_close_injected_client() -> None:
    custom = httpx.Client()
    client = Client(api_key="ak_live_test", http_client=custom)
    client.close()
    assert not custom.is_closed  # caller owns its lifecycle
    custom.close()


# --- N1: user_agent override + default name --------------------------------


@respx.mock
def test_user_agent_override(article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([article], None))
    )
    client = Client(api_key="ak_live_test", user_agent="my-bot/9.9")
    client.news.list()
    assert route.calls[0].request.headers["user-agent"] == "my-bot/9.9"
    client.close()


def test_default_user_agent_name() -> None:
    from alphai._config import USER_AGENT

    assert USER_AGENT.startswith("alphai-sdk-python/")


# --- L1: has_more agrees with the paginator on empty cursor ----------------


def test_has_more_empty_cursor_is_false() -> None:
    assert NewsPagination(results=[], next_cursor="").has_more is False
    assert NewsPagination(results=[], next_cursor=None).has_more is False
    assert NewsPagination(results=[], next_cursor="c2").has_more is True


# --- L2: negative max_retries is clamped -----------------------------------


@respx.mock
def test_negative_max_retries_clamped(article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([article], None))
    )
    client = Client(api_key="ak_live_test", max_retries=-5)
    assert client._config.max_retries == 0
    assert len(client.news.list().results) == 1  # still makes the request
    assert route.call_count == 1
    client.close()


# --- L3: unparseable 2xx body -> InvalidResponseError ----------------------


@respx.mock
def test_non_json_success_body_raises(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/788e477c66f3849b/").mock(
        return_value=httpx.Response(200, text="not json")
    )
    with pytest.raises(InvalidResponseError):
        client.news.get("788e477c66f3849b")


@respx.mock
def test_trending_wrong_type_raises(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/trending/").mock(
        return_value=httpx.Response(200, json={"not": "a list"})
    )
    with pytest.raises(InvalidResponseError):
        client.news.trending()


# --- L4: repeated cursor doesn't loop forever ------------------------------


@respx.mock
def test_repeated_cursor_terminates(client: Client, article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([article], "SAME")),
            httpx.Response(200, json=page([article], "SAME")),  # same cursor again
        ]
    )
    items = list(client.news.iter())
    assert len(items) == 2
    assert route.call_count == 2  # stops instead of refetching "SAME" forever


# --- L5: uid / ticker validation -------------------------------------------


@pytest.mark.parametrize("bad", ["", "abc/def", "x?y", "a b", "a#b", "a%2f"])
def test_invalid_uid_rejected(client: Client, bad: str) -> None:
    with pytest.raises(ValueError):
        client.news.get(bad)


@pytest.mark.parametrize("bad", ["", "NV/DA", "NV DA", "A?B"])
def test_invalid_ticker_rejected(client: Client, bad: str) -> None:
    with pytest.raises(ValueError):
        client.symbols.get(bad)


def test_valid_ticker_with_dot_and_dash_allowed() -> None:
    # BRK.B / BRK-B style tickers must pass validation.
    from alphai._requests import symbol_detail_path

    assert symbol_detail_path("BRK.B") == "/api/symbols/BRK.B/"
    assert symbol_detail_path("BRK-B") == "/api/symbols/BRK-B/"


# --- L6: api_key never in repr ---------------------------------------------


def test_config_repr_hides_api_key() -> None:
    cfg = ClientConfig(api_key="ak_live_supersecret")
    assert "ak_live_supersecret" not in repr(cfg)


# --- build_url helper ------------------------------------------------------


def test_build_url_joins_cleanly() -> None:
    assert build_url("https://api.alphai.io", "/api/news/") == "https://api.alphai.io/api/news/"
    assert build_url("https://api.alphai.io/", "/api/news/") == "https://api.alphai.io/api/news/"
