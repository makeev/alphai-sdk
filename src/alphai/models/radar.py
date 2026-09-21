"""Typed public Radar responses. Unknown fields are preserved."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from .news import _Base

RadarWindow = Literal["4h", "24h"]
RadarScope = Literal["market", "watchlist"]
RadarTier = Literal["free", "basic", "pro"]
RadarMarket = Literal["all", "us_equity", "crypto", "international"]
RadarSort = Literal["score", "stories", "model_stories", "sentiment", "sentiment_change"]
RadarOrder = Literal["asc", "desc"]
RadarSentimentFilter = Literal["all", "positive", "negative", "mixed"]


class RadarCollection(_Base):
    status: Literal["healthy", "unverified"]
    reasons: list[str]
    required_channels: list[str]


class RadarSentiment(_Base):
    value: float | None
    usable_stories: int
    coverage: float | None
    reason: str | None


class RadarCalculationParams(_Base):
    effective_at: int
    window_seconds: int
    baseline_seconds: int
    half_life_seconds: int
    min_relevance: int
    max_story_tickers: int
    prior_stories: float
    min_baseline_stories: int
    min_baseline_days: int
    min_sentiment_stories: int
    min_sentiment_coverage: float
    spike_tail: float


class RadarAccess(_Base):
    tier: RadarTier
    delay_seconds: int
    scope: RadarScope
    watchlist_count: int | None
    watchlist_limit: int | None


class RadarEvidence(_Base):
    uid: str
    title: str
    url: str
    source_domain: str
    time_published: datetime


class RadarReading(_Base):
    ticker: str
    sector: str | None
    market: str | None
    market_exposure_baseline: int
    market_exposure_current: int
    collection: RadarCollection
    stories: int
    articles: int
    outlets: int
    model_stories: int
    model_outlets: int
    baseline_stories: int
    baseline_active_days: int
    stories_per_window_unadjusted: float
    stories_expected: float | None
    tail_probability: float | None
    news_z: float | None
    anomaly_reason: str | None
    candidate_news_spike: bool
    sent: RadarSentiment
    sent_prev: RadarSentiment
    sent_delta: float | None
    evidence_uids: list[str]
    name: str | None
    evidence: list[RadarEvidence]


class RadarSummary(_Base):
    active_tickers: int
    scored_tickers: int
    elevated_tickers: int
    verified_candidates: int
    collection_unverified: int


class RadarFreshness(_Base):
    mode: Literal["historical_preview", "live"] = "historical_preview"
    effective_delay_seconds: int
    generated_at: datetime | None = None
    source_watermark: datetime | None = None
    source_checked_at: datetime | None = None
    unavailable_reason: str | None = None


class RadarWatchlistCoverage(_Base):
    no_recent_news: list[str]
    not_in_snapshot: list[str]


class RadarSnapshot(_Base):
    snapshot_id: str
    methodology_version: str
    research_only: bool = True
    point_in_time: bool = False
    as_of: datetime
    preview_reference_at: datetime | None
    freshness: RadarFreshness
    access: RadarAccess
    window: RadarWindow
    parameters: RadarCalculationParams
    limitations: list[str]
    input_hashes: dict[str, str]
    universe: int
    summary: RadarSummary
    watchlist_coverage: RadarWatchlistCoverage | None
    total: int
    offset: int
    next_offset: int | None
    next_cursor: str | None
    previous_cursor: str | None
    results: list[RadarReading]
