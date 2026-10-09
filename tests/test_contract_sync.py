"""REST-contract sync (API 1.48.0): source/item filters, the 8-K ``filing`` block,
the insider ``is_10b5_1`` filter and event dates, ``symbol_note``, the article
``earnings`` block and the ``tickers`` / ``category`` shortcuts."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from alphai import (
    AsyncClient,
    Client,
    EarningsReport,
    EightKFiling,
    NewsCategory,
    RichNewsArticle,
)

from .conftest import BASE_URL, load, page


def _feed_params(client: Client, **kwargs: Any) -> httpx.QueryParams:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([], None))
    )
    client.news.list(**kwargs)
    return route.calls[0].request.url.params


@respx.mock
def test_list_sends_source_type_single(client: Client) -> None:
    params = _feed_params(client, source_type="sec_form8k")
    assert params.get_list("source_type") == ["sec_form8k"]


@respx.mock
def test_list_sends_source_type_repeated(client: Client) -> None:
    params = _feed_params(client, source_type=["sec_form8k", "sec_form6k"])
    assert params.get_list("source_type") == ["sec_form8k", "sec_form6k"]


@respx.mock
def test_list_sends_item_and_omits_absent_filters(client: Client) -> None:
    params = _feed_params(client, item="5.02")
    assert params["item"] == "5.02"
    assert "source_type" not in params  # the server implies sec_form8k itself


@respx.mock
def test_list_without_source_filters_sends_neither(client: Client) -> None:
    params = _feed_params(client, symbol="NVDA")
    assert "source_type" not in params
    assert "item" not in params


@respx.mock
def test_iter_threads_source_filters_onto_every_page(client: Client) -> None:
    eightk = load("eightk_article")
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page([eightk], "c2")),
            httpx.Response(200, json=page([eightk], None)),
        ]
    )
    items = list(client.news.iter(source_type="sec_form8k", item="1.01"))
    assert len(items) == 2
    for call in route.calls:
        assert call.request.url.params.get_list("source_type") == ["sec_form8k"]
        assert call.request.url.params["item"] == "1.01"
    assert route.calls[1].request.url.params["cursor"] == "c2"


@respx.mock
def test_eightk_row_parses_filing_block(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([load("eightk_article")], None))
    )
    art = client.news.list(source_type="sec_form8k").results[0]
    filing = art.filing
    assert isinstance(filing, EightKFiling)
    assert filing.items == ["1.01", "3.02", "7.01"]
    assert filing.primary_item == "1.01"
    assert filing.accession_number == "0001213900-26-108077"
    assert filing.filed_at == datetime(2026, 10, 8, 21, 27, 1, tzinfo=timezone.utc)
    assert filing.event_date is None
    assert filing.exhibit_url is not None and filing.exhibit_url.endswith("ex99-1.htm")
    # No other structured block on an 8-K row.
    assert art.insider is None
    assert art.earnings is None


def test_filing_block_event_date_and_null_exhibit() -> None:
    filing = EightKFiling.model_validate(
        {
            "items": [],
            "primary_item": None,
            "accession_number": "0000000000-26-000001",
            "filed_at": "2026-09-18T20:05:12Z",
            "event_date": "2026-09-16",
            "exhibit_url": None,
        }
    )
    assert filing.items == []  # header-only filing
    assert filing.event_date == date(2026, 9, 16)
    assert filing.exhibit_url is None


def test_press_row_has_no_filing(article: dict) -> None:
    art = RichNewsArticle.model_validate({**article, "filing": None})
    assert art.filing is None


def test_tickers_and_category_shortcuts(article: dict) -> None:
    art = RichNewsArticle.model_validate(article)
    assert art.tickers == ["NVDA"]
    assert art.tickers is art.enrichment.tickers
    assert art.category is NewsCategory.EARNINGS
    assert art.category == "earnings"


def test_category_shortcut_keeps_unknown_value(article: dict) -> None:
    raw = {**article, "enrichment": {**article["enrichment"], "category": "space_economy"}}
    art = RichNewsArticle.model_validate(raw)
    assert art.category == "space_economy"


def test_shortcuts_are_not_serialized(article: dict) -> None:
    dumped = RichNewsArticle.model_validate(article).model_dump()
    assert "tickers" not in dumped
    assert "category" not in dumped


def test_article_earnings_block_is_typed_and_optional(article: dict) -> None:
    read = load("earnings")["reports"][0]["analysis"]
    art = RichNewsArticle.model_validate({**article, "earnings": read})
    assert isinstance(art.earnings, EarningsReport)
    assert art.earnings.key_metrics
    # Absent on most articles: the default feed never carries it.
    assert RichNewsArticle.model_validate(article).earnings is None


def test_insider_event_filed_at_and_late_filing(insider_article: dict) -> None:
    block = {
        "side": "sell",
        "transaction_code": "S",
        "shares": "30460",
        "avg_price_usd": "222.8",
        "total_value_usd": "6786532.59",
        "is_10b5_1": True,
        "insider_name": "Teter Timothy S.",
        "insider_title": "EVP, General Counsel and Sec",
        "is_officer": True,
        "is_director": False,
        "is_ten_percent_owner": False,
        "transaction_date": "2026-09-21",
        "filed_at": "2026-09-23T20:56:28Z",
        "late_filing": False,
    }
    raw = {**insider_article, "insider": block}
    raw["original"] = {**insider_article["original"], "ownership_form": "indirect"}
    art = RichNewsArticle.model_validate(raw)
    assert art.insider is not None
    assert art.insider.filed_at == datetime(2026, 9, 23, 20, 56, 28, tzinfo=timezone.utc)
    assert art.insider.late_filing is False
    assert art.original.ownership_form == "indirect"


def test_ownership_form_defaults_to_none(article: dict) -> None:
    assert RichNewsArticle.model_validate(article).original.ownership_form is None


@pytest.mark.parametrize(("value", "wire"), [(False, "false"), (True, "true")])
@respx.mock
def test_insider_sends_is_10b5_1(client: Client, value: bool, wire: str) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(200, json=page([], None))
    )
    client.news.insider(symbol="NVDA", is_10b5_1=value)
    assert route.calls[0].request.url.params["is_10b5_1"] == wire


@respx.mock
def test_insider_omits_is_10b5_1_by_default(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(200, json=page([], None))
    )
    client.news.insider()
    assert "is_10b5_1" not in route.calls[0].request.url.params


@respx.mock
def test_insider_iter_threads_is_10b5_1(client: Client, insider_article: dict) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        side_effect=[
            httpx.Response(200, json=page([insider_article], "c2")),
            httpx.Response(200, json=page([], None)),
        ]
    )
    list(client.news.insider_iter(is_10b5_1=False))
    assert [c.request.url.params["is_10b5_1"] for c in route.calls] == ["false", "false"]


@respx.mock
def test_symbol_note_on_feed_page(client: Client) -> None:
    note = "'BTC' is Grayscale Bitcoin Mini Trust ETF. Request BTC-USD for coin news."
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(
            200, json={"results": [], "next_cursor": None, "symbol_note": note}
        )
    )
    assert client.news.list(symbol="BTC").symbol_note == note


@respx.mock
def test_symbol_note_defaults_to_none(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(return_value=httpx.Response(200, json=page([], None)))
    assert client.news.list().symbol_note is None


@respx.mock
async def test_async_list_and_insider_send_new_filters() -> None:
    news = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([load("eightk_article")], None))
    )
    insider = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(200, json=page([], None))
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        result = await client.news.list(source_type=["sec_form8k"], item="1.01")
        await client.news.insider(is_10b5_1=True)
        items = [a async for a in client.news.iter(source_type="gdelt", max_pages=1)]
    assert result.results[0].filing is not None
    assert result.results[0].tickers == ["DAAQ"]
    assert news.calls[0].request.url.params["item"] == "1.01"
    assert news.calls[1].request.url.params.get_list("source_type") == ["gdelt"]
    assert insider.calls[0].request.url.params["is_10b5_1"] == "true"
    assert len(items) == 1
