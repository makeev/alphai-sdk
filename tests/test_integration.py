"""Optional live integration tests against api.alphai.io.

Skipped unless ``ALPHAI_API_KEY`` is set. Run with::

    pytest -m integration

These guard against contract drift between the SDK models and the live API.
"""

from __future__ import annotations

import os

import pytest

from alphai import Client, RichNewsArticle, Symbol

pytestmark = pytest.mark.integration

_HAS_KEY = bool(os.environ.get("ALPHAI_API_KEY"))
_skip = pytest.mark.skipif(not _HAS_KEY, reason="ALPHAI_API_KEY not set")


@_skip
def test_live_news_list() -> None:
    with Client() as client:
        page = client.news.list()
        assert isinstance(page.results, list)
        if page.results:
            assert isinstance(page.results[0], RichNewsArticle)
            assert page.results[0].uid


@_skip
def test_live_trending() -> None:
    with Client() as client:
        items = client.news.trending()
        assert len(items) <= 10


@_skip
def test_live_symbol_and_summaries() -> None:
    with Client() as client:
        sym = client.symbols.get("AAPL")
        assert isinstance(sym, Symbol)
        assert sym.symbol == "AAPL"
        sentiment = client.symbols.sentiment_summary("AAPL")
        assert sentiment.ticker == "AAPL"
        insider = client.symbols.insider_summary("AAPL")
        assert insider.ticker == "AAPL"
