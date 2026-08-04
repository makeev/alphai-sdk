"""News response models — a typed mirror of the OpenAPI ``RichNewsArticle``.

All models allow (and preserve) unknown extra fields so a newer API shape never
breaks parsing. ``raw_text`` is intentionally absent — the API never returns it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, PrivateAttr

from .enums import (
    ActionabilityLike,
    CategoryLike,
    ConfidenceLike,
    NewsCategory,
    SentimentLike,
)


class _Base(BaseModel):
    """Shared config: keep unknown fields, allow population by field name."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Topic(_Base):
    topic: str = ""
    relevance: float = 0.0


class ImpactAnalysis(_Base):
    summary: str = ""
    sentiment: SentimentLike | None = None
    price_impact_prediction: str = ""
    confidence: ConfidenceLike | None = None
    reasoning: str = ""


class TickerAnalysis(_Base):
    ticker: str = ""
    relevance_context: str = ""
    impact_analysis: ImpactAnalysis | None = None


class NewsTradingValue(_Base):
    actionability_score: ActionabilityLike | None = None
    information_novelty: int | None = None
    timing_relevance: str = ""
    market_sentiment_alignment: str = ""
    estimated_read_time: str = ""


class IndirectMarketEffects(_Base):
    sector_implications: str = ""
    regional_market_impact: str = ""
    global_market_relevance: str = ""


class AlternativePerspectives(_Base):
    contrarian_view: str = ""
    overlooked_factors: str = ""


class KeyEntity(_Base):
    name: str = ""
    type: str = ""
    description: str = ""


class AITradingInsights(_Base):
    ticker_analysis: list[TickerAnalysis] = []
    news_trading_value: NewsTradingValue | None = None
    indirect_market_effects: IndirectMarketEffects | None = None
    alternative_perspectives: AlternativePerspectives | None = None


class NewsContextEnhancement(_Base):
    background_context: str = ""
    impact_analysis: str = ""
    key_entities: list[KeyEntity] = []
    market_relevance_summary: str = ""
    estimated_read_time_minutes: int | None = None


class OriginalArticle(_Base):
    """The article as fetched from the source (``original`` block)."""

    id: int | None = None
    uid: str
    title: str = ""
    url: str = ""
    time_published: datetime | None = None
    authors: list[str] = []
    summary: str = ""
    banner_image: str | None = None
    source: str = ""
    source_domain: str = ""
    topics: list[Topic] = []
    # Loosely typed on purpose — the API declares additionalProperties here.
    tickers_sentiment: list[dict[str, Any]] = []
    created_at: datetime | None = None
    updated_at: datetime | None = None


class EnrichedArticle(_Base):
    """The AI enrichment layer (``enrichment`` block)."""

    category: CategoryLike = NewsCategory.OTHER
    tickers: list[str] = []
    relevance_score: int = 0
    ai_trading_insights: AITradingInsights | None = None
    news_context_enhancement: NewsContextEnhancement | None = None


class InsiderEvent(_Base):
    """Structured SEC Form 4 event block (insider-feed items only).

    Aggregate of the row's whole transaction group: ``shares``/``total_value_usd``
    are group sums (a 10b5-1 ladder is one event), ``avg_price_usd`` is the
    value-weighted average over priced tranches (``None`` when the filing prices
    no tranche). ``side`` is ``"buy"`` (P) / ``"sell"`` (S) / ``"other"`` (incl.
    D, sale to issuer); the raw ``transaction_code`` rides along. The API sends
    money fields as decimal strings; pydantic parses them to ``Decimal``.
    """

    side: str = "other"
    transaction_code: str = ""
    shares: Decimal | None = None
    avg_price_usd: Decimal | None = None
    total_value_usd: Decimal | None = None
    is_10b5_1: bool = False
    insider_name: str = ""
    insider_title: str = ""
    is_officer: bool = False
    is_director: bool = False
    is_ten_percent_owner: bool = False
    transaction_date: date | None = None


class RichNewsArticle(_Base):
    """A single enriched article: ``original`` + ``enrichment`` (+ story fields)."""

    original: OriginalArticle
    enrichment: EnrichedArticle
    # Structured Form 4 event block — populated on insider-feed items only
    # (GET /api/news/insider/); None on every other endpoint.
    insider: InsiderEvent | None = None
    # Populated only when listing with collapse_stories=True.
    story_id: str | None = None
    sources_count: int | None = None
    sources: list[str] | None = None

    @property
    def uid(self) -> str:
        """Convenience: the article's identifier (from the live ``original``)."""
        return self.original.uid

    @property
    def title(self) -> str:
        return self.original.title

    @property
    def relevance_score(self) -> int:
        return self.enrichment.relevance_score


class NewsPagination(_Base):
    """A page of the cursor-paginated feed: ``results`` + ``next_cursor``."""

    results: list[RichNewsArticle] = []
    next_cursor: str | None = None

    #: Sort mode that produced this page. NOT part of the response body — the
    #: request layer stamps it (see ``_requests.parse_news_page``) because
    #: "is there more?" has a different answer per mode and the body alone
    #: cannot tell them apart.
    _sort: str = PrivateAttr(default="published")

    @property
    def caught_up(self) -> bool:
        """True when this page exhausted what the mode was asked for.

        ``published``: the feed ended — no ``next_cursor``.

        ``ingested``: nothing arrived since the last poll — empty ``results``.
        In this mode ``next_cursor`` is ALWAYS set (it is a polling position,
        not an end-of-feed marker), so it carries no termination signal at all
        and must not be used as one.
        """
        if self._sort == "ingested":
            return not self.results
        # Empty-string cursor counts as "no more", matching the paginator.
        return not self.next_cursor

    @property
    def has_more(self) -> bool:
        """True when another page is worth fetching — the inverse of
        :attr:`caught_up`.

        In ``published`` mode that means an older page exists. In ``ingested``
        mode it means this poll returned rows, so there may be more waiting;
        a caught-up poll reports ``False``.
        """
        return not self.caught_up


__all__ = [
    "AITradingInsights",
    "AlternativePerspectives",
    "EnrichedArticle",
    "ImpactAnalysis",
    "IndirectMarketEffects",
    "KeyEntity",
    "NewsContextEnhancement",
    "NewsPagination",
    "NewsTradingValue",
    "OriginalArticle",
    "RichNewsArticle",
    "TickerAnalysis",
    "Topic",
]
