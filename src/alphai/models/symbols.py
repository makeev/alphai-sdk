"""Symbol response models — Symbol, sentiment summary, insider summary.

Money fields arrive as decimal strings in JSON; Pydantic coerces them to
``Decimal`` so callers never lose precision.
"""

from __future__ import annotations

from datetime import date
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


__all__ = [
    "DailySentimentBucket",
    "Symbol",
    "TickerInsiderSummary",
    "TickerSentimentSummary",
    "TopInsider",
]
