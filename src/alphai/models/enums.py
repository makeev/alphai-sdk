"""API enums and forward-compatible enum-or-string type aliases.

The API may add new category / sentiment / event-type values over time. To keep
an older SDK from breaking on a value it doesn't know, the model fields use the
``*Like`` aliases below: a known value is coerced to the enum member (great for
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


class CorporateEventType(str, Enum):
    """What a filing or release is about, first of all (``event.type``).

    One type per row; other events the same document reports are listed in
    ``event.also``. Also the vocabulary of the feed's ``event_type`` filter.
    """

    #: A results release. Its numbers are in the article's ``earnings`` block.
    EARNINGS = "earnings"
    #: The date of an upcoming report or call.
    EARNINGS_DATE = "earnings_date"
    #: An officer or director appointed or leaving.
    EXEC_CHANGE = "exec_change"
    #: An acquisition, merger or divestiture.
    M_AND_A = "m_and_a"
    #: A sale of shares, units, warrants or convertible notes (dilution).
    OFFERING = "offering"
    #: A loan, credit facility or non-convertible notes.
    DEBT_FINANCING = "debt_financing"
    DIVIDEND = "dividend"
    BUYBACK = "buyback"
    #: A customer contract, order, licence or supply agreement.
    CONTRACT_AWARD = "contract_award"
    #: An outlook raised, lowered, reaffirmed, withdrawn or initiated.
    GUIDANCE_UPDATE = "guidance_update"
    #: Forward or reverse.
    STOCK_SPLIT = "stock_split"
    #: An exchange deficiency notice, regained compliance, delisting or transfer.
    LISTING_NOTICE = "listing_notice"
    #: Results of a shareholder meeting.
    SHAREHOLDER_VOTE = "shareholder_vote"
    BANKRUPTCY = "bankruptcy"
    #: Layoffs or an exit plan with charges.
    RESTRUCTURING = "restructuring"
    #: Trial data or a regulator's decision on a product.
    CLINICAL_REGULATORY = "clinical_regulatory"
    #: None of the above.
    OTHER = "other"


# Forward-compatible aliases: try the enum first, fall back to a raw string.
CategoryLike = Annotated[NewsCategory | str, Field(union_mode="left_to_right")]
EventTypeLike = Annotated[CorporateEventType | str, Field(union_mode="left_to_right")]
SentimentLike = Annotated[Sentiment | str, Field(union_mode="left_to_right")]
ConfidenceLike = Annotated[Confidence | str, Field(union_mode="left_to_right")]
ActionabilityLike = Annotated[Actionability | str, Field(union_mode="left_to_right")]


__all__ = [
    "Actionability",
    "ActionabilityLike",
    "CategoryLike",
    "Confidence",
    "ConfidenceLike",
    "CorporateEventType",
    "EventTypeLike",
    "NewsCategory",
    "Sentiment",
    "SentimentLike",
]
