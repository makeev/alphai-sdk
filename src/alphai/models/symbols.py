"""Symbol response models — Symbol, sentiment summary, insider summary, earnings.

Money fields arrive as decimal strings in JSON; Pydantic coerces them to
``Decimal`` so callers never lose precision.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class Symbol(_Base):
    """An active symbol — a US equity/ETF, a cryptocurrency, or a foreign listing.

    List responses omit ``description``/``website``; both list and detail carry
    the multi-market fields below.

    Multi-market metadata:

    - ``asset_type`` is ``"Stock"``, ``"ETF"``, or ``"Crypto"``.
    - ``country`` (ISO alpha-2) and ``currency`` are populated for foreign and
      crypto listings, and empty for US equities.
    - ``supports_insider`` is ``True`` only for US SEC names that can have Form 4
      insider data; ``False`` for cryptocurrencies and foreign listings.
    - ``tv_symbol`` is an optional TradingView-symbol override (usually empty).
    - ``next_report_date`` is the company-confirmed date of the next earnings
      report (America/New_York), or ``None`` when AlphaAI holds no confirmed
      date — never an estimate; detail responses only.

    Crypto tickers carry a ``-USD`` quote suffix (e.g. ``BTC-USD``); foreign
    listings use the Yahoo-suffix form (e.g. ``VOD.L``).
    """

    symbol: str
    name: str = ""
    asset_type: str = ""
    exchange: str = ""
    sector: str = ""
    industry: str = ""
    country: str = ""
    currency: str = ""
    supports_insider: bool = True
    tv_symbol: str = ""
    next_report_date: date | None = None
    description: str = ""
    website: str | None = None


class DailySentimentBucket(_Base):
    day: date
    bullish: int = 0
    neutral: int = 0
    bearish: int = 0


class TickerSentimentSummary(_Base):
    """7-day rollup of per-ticker AI sentiment from press coverage."""

    ticker: str
    days: int = 0
    total: int = 0
    bullish: int = 0
    neutral: int = 0
    bearish: int = 0
    daily: list[DailySentimentBucket] = []


class TopInsider(_Base):
    name: str = ""
    title: str = ""
    transaction_count: int = 0
    net_value: Decimal | None = None


class TickerInsiderSummary(_Base):
    """30-day rollup of SEC Form 4 insider activity for one ticker."""

    ticker: str
    days: int = 0
    total_transactions: int = 0
    buy_count: int = 0
    sell_count: int = 0
    buy_value_usd: Decimal | None = None
    sell_value_usd: Decimal | None = None
    pct_10b5_1: int = 0
    top_insiders: list[TopInsider] = []


class KeyMetric(_Base):
    """One headline figure from an earnings release, as reported."""

    name: str = ""
    value: str = ""
    basis: str = ""
    prior_year: str | None = None
    prior_quarter: str | None = None
    yoy_change: str | None = None
    qoq_change: str | None = None


class Segment(_Base):
    """One reporting segment and what drove it."""

    name: str = ""
    revenue: str = ""
    yoy_change: str | None = None
    qoq_change: str | None = None
    driver: str = ""


class Guidance(_Base):
    """Company guidance for the coming period (``None`` when not disclosed)."""

    period: str = ""
    revenue: str | None = None
    gross_margin: str | None = None
    operating_expenses: str | None = None
    tax_rate: str | None = None
    other: list[str] = []


class VsPriorGuidance(_Base):
    """A reported figure against the company's own prior outlook."""

    metric: str = ""
    prior_guidance: str = ""
    actual: str = ""
    verdict: str = ""


class Quote(_Base):
    """A management quote surfaced from the filing."""

    speaker: str = ""
    role: str | None = None
    text: str = ""


class EarningsReport(_Base):
    """AlphaAI's structured read of an earnings release (the ``analysis`` object).

    Produced from the company's own SEC filing — an 8-K item 2.02 for US
    filers, a 6-K earnings release for foreign private issuers — with every
    figure checked against the filing text; consensus estimates and price
    targets are deliberately absent.
    """

    company: str = ""
    ticker: str = ""
    fiscal_period: str = ""
    period_end: str | None = None
    headline: str = ""
    verdict: str = ""
    verdict_reason: str = ""
    key_metrics: list[KeyMetric] = []
    segments: list[Segment] = []
    guidance: Guidance | None = None
    vs_prior_guidance: list[VsPriorGuidance] = []
    capital_returns: list[str] = []
    balance_sheet_cash_flow: list[str] = []
    drivers: list[str] = []
    concerns: list[str] = []
    what_to_watch: list[str] = []
    quotes: list[Quote] = []
    analysis: str = ""
    missing_items: list[str] = []
    numbers_verified_from_document: bool = False


class EarningsRead(_Base):
    """One published earnings read in a ticker's history.

    ``source_type`` is ``sec_form8k`` for a US filer's item 2.02 and
    ``sec_form6k`` for a foreign private issuer's earnings release. ``ticker``
    is the share class the filing was made under, which share-class bridging
    may render as a class you did not ask for.
    """

    uid: str
    time_published: datetime
    title: str = ""
    source_type: str = ""
    ticker: str = ""
    fiscal_period: str = ""
    analysis: EarningsReport | None = None


class LatestEarningsPointer(_Base):
    """Pointer to a ticker's most recent earnings read (for the article link)."""

    uid: str
    time_published: datetime
    title: str = ""
    fiscal_period: str = ""
    verdict: str = ""
    headline: str = ""


class TickerEarningsHistory(_Base):
    """A ticker's published earnings reads, newest first, plus its next report date.

    ``reports`` is capped at 20 and may be empty — a normal answer, not an
    error: it means no read has been published yet. ``next_report_date`` is the
    company-confirmed date of the next report (``None`` when unconfirmed; never
    an estimate).
    """

    ticker: str
    reports: list[EarningsRead] = []
    next_report_date: date | None = None


__all__ = [
    "DailySentimentBucket",
    "EarningsRead",
    "EarningsReport",
    "Guidance",
    "KeyMetric",
    "LatestEarningsPointer",
    "Quote",
    "Segment",
    "Symbol",
    "TickerEarningsHistory",
    "TickerInsiderSummary",
    "TickerSentimentSummary",
    "TopInsider",
    "VsPriorGuidance",
]
