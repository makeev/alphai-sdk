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


class InsiderDecision(str, Enum):
    """Was a Form 4 sale the insider's own decision (``insider.decision``).

    Read from the whole filing, not only from the 10b5-1 checkbox. Only sales
    (``transaction_code`` ``"S"``) are labelled: purchases, a sale to the
    issuer (``"D"``) and other codes carry ``None``. Also the vocabulary of the
    insider feed's ``decision`` filter.
    """

    #: The insider chose to sell: no plan or paperwork explains the sale.
    DISCRETIONARY = "discretionary"
    #: The sale follows from a 10b5-1 plan or from paperwork, such as shares
    #: sold to pay the tax on vesting or to cover an option exercise.
    PLAN_LIKE = "plan_like"
    #: The filing does not let the two be told apart.
    UNKNOWN = "unknown"


class InsiderDecisionReason(str, Enum):
    """Why a Form 4 sale got its ``decision`` (``insider.decision_reason``).

    Each reason belongs to one :class:`InsiderDecision` value; the members are
    grouped by it below.
    """

    # --- with ``plan_like`` ---
    #: The 10b5-1 checkbox, or a footnote that places the sale under a
    #: pre-arranged plan, so it can appear with ``is_10b5_1=False``.
    PLAN_10B5_1 = "plan_10b5_1"
    #: Shares sold to pay the tax on vesting.
    TAX_WITHHOLDING = "tax_withholding"
    #: The sale covers the cost of an option exercise and its tax.
    EXERCISE_COVER = "exercise_cover"
    #: A footnote says the sale was automatic or outside the insider's
    #: discretion.
    STATED_NON_DISCRETIONARY = "stated_non_discretionary"

    # --- with ``discretionary`` ---
    #: No plan or paperwork explains the sale: nothing in the filing points to
    #: one, or the sale is far larger than what vested or was exercised.
    OPEN_MARKET = "open_market"
    #: Options exercised and the exercised shares sold, beyond what covering
    #: the exercise needs.
    EXERCISE_AND_SELL = "exercise_and_sell"
    #: The shares sold plus those withheld for tax cover everything that vested.
    SOLD_ALL_VESTED = "sold_all_vested"

    # --- with ``unknown`` ---
    #: Part of the newly vested shares sold, more than the tax alone would
    #: need, or on top of tax already withheld.
    PARTIAL_VEST_SALE = "partial_vest_sale"
    #: The sale could be an exercise cover at a high tax rate or a choice.
    COVER_AMBIGUOUS = "cover_ambiguous"
    #: The filing both vests shares and exercises options, so the sale cannot
    #: be tied to either.
    MIXED_ACQUISITIONS = "mixed_acquisitions"
    #: The filed price failed a price check, so the arithmetic is not trusted.
    PRICE_DISPUTED = "price_disputed"
    #: The rest of the filing is not held.
    NO_LINES = "no_lines"


# Forward-compatible aliases: try the enum first, fall back to a raw string.
CategoryLike = Annotated[NewsCategory | str, Field(union_mode="left_to_right")]
EventTypeLike = Annotated[CorporateEventType | str, Field(union_mode="left_to_right")]
InsiderDecisionLike = Annotated[InsiderDecision | str, Field(union_mode="left_to_right")]
InsiderDecisionReasonLike = Annotated[
    InsiderDecisionReason | str, Field(union_mode="left_to_right")
]
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
    "InsiderDecision",
    "InsiderDecisionLike",
    "InsiderDecisionReason",
    "InsiderDecisionReasonLike",
    "NewsCategory",
    "Sentiment",
    "SentimentLike",
]
