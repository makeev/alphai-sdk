"""Typed public Brief responses. Unknown fields are preserved."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from .news import _Base


class BriefSignal(_Base):
    ticker: str
    sentiment: str | None = None


class BriefEvent(_Base):
    uid: str
    story_id: str
    title: str
    summary: str
    url: str
    article_url: str
    source_domain: str
    source_type: str
    time_published: datetime
    matched_tickers: list[str]
    category: str
    relevance_score: int
    information_novelty: int | None = None
    actionability: str | None = None
    signals: list[BriefSignal] = Field(default_factory=list)
    earnings_available: bool = False


class BriefEarningsDate(_Base):
    ticker: str
    report_date: date


class NewsBrief(_Base):
    generated_at: datetime
    window_start: datetime
    window_end: datetime
    hours: int
    tickers: list[str]
    unknown_tickers: list[str]
    events: list[BriefEvent]
    filings: list[BriefEvent]
    upcoming_earnings: list[BriefEarningsDate]
    events_truncated: bool = False
    filings_truncated: bool = False
