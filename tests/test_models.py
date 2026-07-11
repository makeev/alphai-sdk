"""Model parsing: nested enrichment, enums, Decimal money, forward-compat."""

from __future__ import annotations

from decimal import Decimal

from alphai import (
    Actionability,
    Confidence,
    NewsCategory,
    RichNewsArticle,
    Sentiment,
    TickerInsiderSummary,
)

from .conftest import load


def test_rich_article_parses_full_tree(article: dict) -> None:
    art = RichNewsArticle.model_validate(article)
    assert art.uid == "788e477c66f3849b"
    assert art.title.startswith("NVIDIA")
    assert art.relevance_score == 9
    assert art.enrichment.category is NewsCategory.EARNINGS
    assert art.enrichment.tickers == ["NVDA"]

    insights = art.enrichment.ai_trading_insights
    assert insights is not None
    ta = insights.ticker_analysis[0]
    assert ta.ticker == "NVDA"
    assert ta.impact_analysis is not None
    assert ta.impact_analysis.sentiment is Sentiment.POSITIVE
    assert ta.impact_analysis.confidence is Confidence.HIGH

    ntv = insights.news_trading_value
    assert ntv is not None
    assert ntv.actionability_score is Actionability.HIGH
    assert ntv.information_novelty == 8

    nce = art.enrichment.news_context_enhancement
    assert nce is not None
    assert nce.key_entities[0].name == "NVIDIA"
    assert nce.estimated_read_time_minutes == 3


def test_original_block_has_no_raw_text(article: dict) -> None:
    art = RichNewsArticle.model_validate(article)
    dumped = art.original.model_dump()
    assert "raw_text" not in dumped


def test_topics_and_tickers_sentiment(article: dict) -> None:
    art = RichNewsArticle.model_validate(article)
    assert art.original.topics[0].topic == "earnings"
    # tickers_sentiment is intentionally loose (list of dicts)
    assert art.original.tickers_sentiment[0]["ticker"] == "NVDA"


def test_unknown_category_passes_through_as_str() -> None:
    art = RichNewsArticle.model_validate(
        {"original": {"uid": "0" * 16}, "enrichment": {"category": "brand_new_cat"}}
    )
    assert art.enrichment.category == "brand_new_cat"
    assert isinstance(art.enrichment.category, str)
    assert not isinstance(art.enrichment.category, NewsCategory)


def test_extra_fields_are_preserved() -> None:
    art = RichNewsArticle.model_validate(
        {"original": {"uid": "0" * 16, "future_field": 42}, "enrichment": {}}
    )
    assert art.original.model_extra == {"future_field": 42}


def test_insider_summary_money_is_decimal() -> None:
    summ = TickerInsiderSummary.model_validate(load("insider_summary"))
    assert summ.buy_value_usd == Decimal("1240000.00")
    assert summ.sell_value_usd == Decimal("224580213.05")
    assert isinstance(summ.buy_value_usd, Decimal)
    assert summ.top_insiders[0].net_value == Decimal("-221102600.00")
    assert summ.pct_10b5_1 == 78


def test_insider_summary_null_money_stays_none() -> None:
    summ = TickerInsiderSummary.model_validate(
        {"ticker": "ZZZZ", "days": 30, "buy_value_usd": None, "top_insiders": []}
    )
    assert summ.buy_value_usd is None


def test_insider_event_block_parses():
    from datetime import date
    from decimal import Decimal

    from alphai.models import InsiderEvent, RichNewsArticle

    payload = {
        "original": {"uid": "f4abc12345678901", "title": "Insider sale"},
        "enrichment": {"category": "insider", "tickers": ["CRWV"], "relevance_score": 6},
        "insider": {
            "side": "sell",
            "transaction_code": "S",
            "shares": "4000",
            "avg_price_usd": "175",
            "total_value_usd": "700000",
            "is_10b5_1": True,
            "insider_name": "STEVENS MARK A",
            "insider_title": "Director",
            "is_officer": False,
            "is_director": True,
            "is_ten_percent_owner": False,
            "transaction_date": "2026-07-09",
        },
    }
    article = RichNewsArticle.model_validate(payload)
    assert isinstance(article.insider, InsiderEvent)
    assert article.insider.side == "sell"
    assert article.insider.shares == Decimal("4000")
    assert article.insider.avg_price_usd == Decimal("175")
    assert article.insider.transaction_date == date(2026, 7, 9)


def test_insider_block_absent_is_none():
    from alphai.models import RichNewsArticle

    article = RichNewsArticle.model_validate({"original": {"uid": "a" * 16}, "enrichment": {}})
    assert article.insider is None
