"""Insider cluster buys — episodes in which several different insiders of one
issuer bought on the open market together (``GET /api/news/insider/clusters/``).

Money fields arrive as decimal strings in JSON; Pydantic coerces them to
``Decimal`` so callers never lose precision.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict

#: The episode's verdict. ``open_market``: at least two independent buyers remain
#: and one of them is an officer or director. ``holders_only``: only 10% holders
#: without a role remain. ``plan_or_offering``: fewer than two independent
#: buyers — an IPO or PIPE allocation, a plan lot, duplicate reporters.
ClusterPattern = Literal["open_market", "plan_or_offering", "holders_only"]

#: Why a buyer does or does not count toward the cluster.
ClusterBuyerRole = Literal["independent", "plan_like", "unpriced", "duplicate_of"]

#: Set on a ``plan_like`` buyer when the Form 4's own footnotes decided it.
ClusterBuyerReason = Literal["placement", "offering", "private"]


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class ClusterBuyer(_Base):
    """One reporting owner inside an episode and the role the rule gave them.

    ``independent`` buyers are the cluster. ``plan_like``: the buyer's fills all
    share an exact date-and-price pair with another buyer's (an allocation, an
    ESPP/DRIP lot), match another direct holder's lot at a round price, or the
    filing itself says the shares were not bought on the open market (then
    ``reason`` is set). ``unpriced``: no fill carries a price (units, exchanges).
    ``duplicate_of``: the same transaction another reporter already reported;
    ``duplicate_of`` names that reporter.
    """

    name: str
    #: ``""`` when the person is a director only.
    title: str = ""
    is_officer: bool = False
    is_director: bool = False
    is_ten_percent_owner: bool = False
    role: ClusterBuyerRole
    #: ``placement`` — bought from the issuer (a PIPE, a subscription or
    #: securities purchase agreement, SPAC sponsor units); ``offering`` —
    #: allocated in a public offering or IPO; ``private`` — a negotiated block
    #: from another holder. ``None`` when the price shape alone decided the role.
    reason: ClusterBuyerReason | None = None
    duplicate_of: str | None = None
    fills: int = 0
    #: Sum of this buyer's priced fills, USD; ``None`` when none carries a price.
    usd: Decimal | None = None
    first_date: date
    last_date: date
    #: The ``uid`` s of the insider news rows fronting this buyer's filings —
    #: ``client.news.get(uid)`` opens the event.
    news_uids: list[str] = []


class ClusterFiling(_Base):
    """One Form 4 behind the episode, with its EDGAR index page."""

    accession_number: str
    filed_at: datetime
    sec_url: str


class InsiderCluster(_Base):
    """One issuer's run of Form 4 purchases and its verdict.

    ``buyers`` counts independent buyers (the cluster); ``buyers_total``
    everyone who bought, including plan, unpriced and duplicate reporters.
    ``known_at`` is when the episode's latest filing reached EDGAR — the clock
    the ``days`` filter is measured on.
    """

    ticker: str
    name: str
    #: SEC Central Index Key of the issuer.
    cik: int
    #: First and last purchase date of the episode.
    window_start: date
    window_end: date
    known_at: datetime
    buyers: int = 0
    buyers_total: int = 0
    officer_director_buyers: int = 0
    ten_percent_owner_buyers: int = 0
    #: Purchase tranches counted (a transaction reported twice is counted once).
    fills: int = 0
    #: Distinct Form 4 filings.
    filings: int = 0
    #: Sum of the counted tranches' values, USD; ``None`` when no tranche
    #: carries a price.
    total_usd: Decimal | None = None
    #: ``True`` when at least one counted tranche has no price, so ``total_usd``
    #: understates the episode.
    value_partial: bool = False
    distinct_dates: int = 0
    #: Distinct prices to the cent across priced tranches.
    distinct_prices: int = 0
    pattern: ClusterPattern
    #: Machine-readable notes behind the verdict: ``mass_uniform_date_price``,
    #: ``same_price_across_dates``, ``one_price_multi_date``,
    #: ``plan_like_buyers``, ``off_market_buyers``, ``unpriced_buyers``,
    #: ``duplicate_filings``, ``no_officer_or_director``.
    pattern_reasons: list[str] = []
    buyers_detail: list[ClusterBuyer] = []
    filings_detail: list[ClusterFiling] = []


class InsiderClustersMeta(_Base):
    """What the list is and is not: a descriptive screen, not point-in-time."""

    #: When the underlying computation ran (refreshed every few minutes).
    as_of: datetime
    #: Earliest purchase date on record; nothing before it can appear.
    coverage_since: date | None = None
    episode_gap_days: int = 10
    episode_max_days: int = 30
    research_only: bool = True
    point_in_time: bool = False


class InsiderClustersPage(_Base):
    """A page of classified purchase episodes: ``results`` + ``next_cursor`` + ``meta``."""

    results: list[InsiderCluster] = []
    #: Opaque cursor for the next page (pass back with the same ``sort``);
    #: ``None`` at the end.
    next_cursor: str | None = None
    meta: InsiderClustersMeta
