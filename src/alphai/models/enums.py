"""API enums and forward-compatible enum-or-string type aliases.

The API may add new category / sentiment values over time. To keep an older SDK
from breaking on a value it doesn't know, the model fields use the ``*Like``
aliases below: a known value is coerced to the enum member (great for
autocomplete and ``==`` checks), while an unknown value passes through untouched
as a plain ``str``.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated

from pydantic import Field


class NewsCategory(str, Enum):
    """The 14 enrichment categories assigned to every article."""

    EARNINGS = "earnings"
    MERGERS_ACQUISITIONS = "mergers_acquisitions"
    REGULATION = "regulation"
    MACRO_ECONOMY = "macro_economy"
    SECTOR_ANALYSIS = "sector_analysis"
    MARKET_MOVERS = "market_movers"
    TECHNOLOGY = "technology"
    COMMODITIES = "commodities"
    CRYPTO = "crypto"
    IPO = "ipo"
    GEOPOLITICS = "geopolitics"
    INSIDER = "insider"
    CORPORATE_ACTIONS = "corporate_actions"
    OTHER = "other"


class Sentiment(str, Enum):
    """Per-ticker LLM sentiment on the impact analysis."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Confidence(str, Enum):
    """Model confidence on a per-ticker impact prediction."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Actionability(str, Enum):
    """How tradeable the article is, on the news-trading-value block."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NEGLIGIBLE = "negligible"


# Forward-compatible aliases: try the enum first, fall back to a raw string.
CategoryLike = Annotated[NewsCategory | str, Field(union_mode="left_to_right")]
SentimentLike = Annotated[Sentiment | str, Field(union_mode="left_to_right")]
ConfidenceLike = Annotated[Confidence | str, Field(union_mode="left_to_right")]
ActionabilityLike = Annotated[Actionability | str, Field(union_mode="left_to_right")]


__all__ = [
    "Actionability",
    "ActionabilityLike",
    "CategoryLike",
    "Confidence",
    "ConfidenceLike",
    "NewsCategory",
    "Sentiment",
    "SentimentLike",
]
