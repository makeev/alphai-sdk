"""News response models — a typed mirror of the OpenAPI ``RichNewsArticle``.

All models allow (and preserve) unknown extra fields so a newer API shape never
breaks parsing. ``raw_text`` is intentionally absent — the API never returns it.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, PrivateAttr

from .enums import (
    ActionabilityLike,
    CategoryLike,
    ConfidenceLike,
    NewsCategory,
    SentimentLike,
)
from .symbols import EarningsReport


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
    # SEC Form 4 rows only: the holding pool the trade touched (``"direct"`` /
    # ``"indirect"``); ``None`` on other news. One filing can surface both legs
    # as two rows with the same URL; they are separate events, so sum them.
    ownership_form: str | None = None
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
    #: When EDGAR accepted the filing (UTC); compare with ``transaction_date``.
    filed_at: datetime | None = None
    #: The filing missed the SEC's two-business-day deadline (Rule 16a-3(g)),
    #: counted on Eastern dates with one weekday of slack.
    late_filing: bool = False


class EightKFiling(_Base):
    """Structured SEC 8-K filing block (``filing``), on rows whose source is an 8-K.

    What the filing itself says, next to the AI read of it: every ``items``
    code in the filing's order (``["5.02", "9.01"]``; the ``item=`` filter
    matches any of them, and the list is empty for a filing SEC served no
    document for), the ``primary_item`` that drove the row's category, the
    ``accession_number`` to cite, when EDGAR accepted it (``filed_at``), the
    date of the event it reports (``event_date``, which can precede the filing
    by up to four business days) and the press-release exhibit the summary was
    built from (``exhibit_url``, ``None`` when the filing has none).
    """

    items: list[str] = []
    primary_item: str | None = None
    accession_number: str = ""
    filed_at: datetime | None = None
    event_date: date | None = None
    exhibit_url: str | None = None


class SearchMatch(_Base):
    """Why a search result matched. Scores are comparable within one response only."""

    score: float
    terms_matched: int | None = None
    context: str | None = None


class NewsSearchQueryInfo(_Base):
    """The server's interpretation of the text and the effective archive window."""

    mode: Literal["strict", "broadened", "no_match", "no_terms"]
    sort: Literal["relevance", "published"]
    terms: list[str]
    required_terms: list[str] = []
    optional_terms: list[str] = []
    window_from: datetime | None = None
    note: str = ""


class RichNewsArticle(_Base):
    """A single enriched article: ``original`` + ``enrichment`` (+ story fields)."""

    original: OriginalArticle
    enrichment: EnrichedArticle
    # Search endpoint only; context can be absent for title/entity-only matches.
    search_match: SearchMatch | None = None
    # Structured Form 4 event block — on Form 4 rows of the insider feed
    # (GET /api/news/insider/) and of GET /api/news/{uid}/; None elsewhere.
    insider: InsiderEvent | None = None
    # Structured 8-K filing block — on 8-K rows of GET /api/news/ and of
    # GET /api/news/{uid}/; None on press, Form 4 and 6-K rows and elsewhere.
    filing: EightKFiling | None = None
    # AlphAI's structured earnings read — GET /api/news/{uid}/ only, and only on
    # a major ticker's earnings filing whose figures cleared the cross-check
    # against the filing text. None on every other article: guard before use.
    earnings: EarningsReport | None = None
    # The story this article belongs to: a permanent key (the uid of the story's
    # first root article), filled on every row since API 1.49.0; a lone article
    # names itself. Resolve it with ``client.stories.get(story_id)``. None only
    # on ``/api/news/{uid}/related/``.
    story_id: str | None = None
    # Populated only when listing with collapse_stories=True.
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

    @property
    def tickers(self) -> list[str]:
        """Convenience: the validated tickers (``enrichment.tickers``)."""
        return self.enrichment.tickers

    @property
    def category(self) -> NewsCategory | str:
        """Convenience: the category (``enrichment.category``); a
        :class:`NewsCategory` member, or the raw string for a value this SDK
        version does not know yet."""
        return self.enrichment.category


class NewsPagination(_Base):
    """A page of the cursor-paginated feed: ``results`` + ``next_cursor``."""

    results: list[RichNewsArticle] = []
    next_cursor: str | None = None
    #: Set only when ``symbol`` named a stock/ETF whose bare string also names
    #: an active cryptocurrency (``BTC`` is a Grayscale ETF): one sentence naming
    #: the coin ticker to request (``BTC-USD``). The page still serves the equity.
    symbol_note: str | None = None

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


class NewsSearchPage(NewsPagination):
    """Ranked search page. ``matched`` is bounded to the best 200, not a corpus total.

    Inspect ``query`` before treating an empty or broadened result as evidence.
    Continue with ``next_cursor`` and the same query, filters and window.
    """

    count: int
    matched: int
    query: NewsSearchQueryInfo


class InsiderCsvExport(_Base):
    """An insider-feed CSV export (``news.insider_csv``): the file and how it ended.

    ``text`` is the whole file (header line first; columns in the order the
    API documents). ``rows`` counts data rows and ``row_cap`` is the plan's
    cap. ``truncated`` says why the file stopped: ``"row_cap"`` (more rows
    exist; pass ``next_cursor`` back as ``cursor``) or ``"archive_horizon"``
    (the walk reached the plan's archive depth); ``None`` when the file holds
    everything the filters select. ``next_cursor`` is the same token a JSON
    page would return at that position, so it continues in either format.
    """

    text: str
    rows: int | None = None
    row_cap: int | None = None
    truncated: str | None = None
    next_cursor: str | None = None
    filename: str | None = None


__all__ = [
    "AITradingInsights",
    "AlternativePerspectives",
    "EightKFiling",
    "EnrichedArticle",
    "ImpactAnalysis",
    "IndirectMarketEffects",
    "InsiderCsvExport",
    "InsiderEvent",
    "KeyEntity",
    "NewsContextEnhancement",
    "NewsPagination",
    "NewsSearchPage",
    "NewsSearchQueryInfo",
    "NewsTradingValue",
    "OriginalArticle",
    "RichNewsArticle",
    "SearchMatch",
    "TickerAnalysis",
    "Topic",
]
