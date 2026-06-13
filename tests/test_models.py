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
