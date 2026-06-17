"""Symbol endpoint coverage (sync) via respx."""

from __future__ import annotations

from decimal import Decimal

import httpx
import respx

from alphai import Client

from .conftest import BASE_URL, load


@respx.mock
def test_symbols_list(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/symbols/").mock(
        return_value=httpx.Response(200, json=load("symbols_list"))
    )
    symbols = client.symbols.list(limit=3, offset=0)
    assert [s.symbol for s in symbols] == ["AAPL", "NVDA", "SPY", "BTC-USD", "VOD.L"]
    assert symbols[2].asset_type == "ETF"
    sent = str(route.calls[0].request.url)
    assert "limit=3" in sent and "offset=0" in sent

    # Multi-market metadata: US equities support Form 4 insider data and carry
    # no country/currency; crypto and foreign listings do the opposite.
    aapl = symbols[0]
    assert aapl.supports_insider is True
    assert aapl.country == "" and aapl.currency == ""
    btc = symbols[3]
    assert btc.asset_type == "Crypto"
    assert btc.currency == "USD" and btc.supports_insider is False
    vod = symbols[4]
    assert vod.country == "GB" and vod.currency == "GBP"
    assert vod.supports_insider is False


@respx.mock
def test_symbols_list_no_params_sends_none(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/symbols/").mock(
        return_value=httpx.Response(200, json=load("symbols_list"))
    )
    client.symbols.list()
    assert route.calls[0].request.url.query == b""


@respx.mock
def test_symbol_get(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/symbols/NVDA/").mock(
        return_value=httpx.Response(200, json=load("symbol"))
    )
    sym = client.symbols.get("NVDA")
    assert sym.symbol == "NVDA"
    assert sym.exchange == "NASDAQ"
    assert sym.website == "https://www.nvidia.com"
    assert sym.supports_insider is True
    assert sym.country == "" and sym.tv_symbol == ""


@respx.mock
def test_sentiment_summary(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/symbols/NVDA/sentiment-summary/").mock(
        return_value=httpx.Response(200, json=load("sentiment_summary"))
    )
    summ = client.symbols.sentiment_summary("NVDA")
    assert summ.days == 7
    assert summ.total == 42
    assert summ.bullish == 25
    assert summ.daily[0].day.isoformat() == "2026-05-18"


@respx.mock
def test_insider_summary(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/symbols/NVDA/insider-summary/").mock(
        return_value=httpx.Response(200, json=load("insider_summary"))
    )
    summ = client.symbols.insider_summary("NVDA")
    assert summ.days == 30
    assert summ.buy_value_usd == Decimal("1240000.00")
    assert summ.top_insiders[0].name == "HUANG JEN HSUN"
    assert summ.top_insiders[0].net_value == Decimal("-221102600.00")
