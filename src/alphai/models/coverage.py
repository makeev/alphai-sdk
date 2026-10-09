"""Coverage passport models (``GET /api/coverage/``).

What each data source holds, from when, and with which caveats: read it before a
backtest or before promising coverage downstream.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class CoverageArchiveDays(_Base):
    """How far back a key on each plan can page the news feeds into a source's
    rows, in days; ``0`` means unlimited."""

    free: int
    basic: int
    pro: int


class CoverageChannel(_Base):
    """One discovery channel of publisher news (``gkg`` / ``rss``)."""

    channel: str
    cadence: str = ""
    last_ingested_at: datetime | None = None
    stale_after_seconds: int | None = None
    stale: bool


class CoverageSource(_Base):
    """The passport of one data source.

    ``source`` is one of ``publisher_news``, ``sec_form4``, ``sec_form8k``,
    ``sec_form6k``, ``earnings_reads``, ``earnings_schedule``,
    ``economic_calendar``. ``first_row_at`` is the earliest row held by the
    source's own clock, NOT the start of dense coverage: ``history_note`` says
    where the history is thin. ``rows_total`` is in the source's own unit
    (articles, distinct filings, reads, confirmed dates, occurrences).
    ``stale`` is an honest flag, not an alert: the newest ingest is older than
    ``stale_after_seconds`` (or, for the economic calendar, no future
    occurrence is held). ``archive_days`` is ``None`` where the archive gate
    does not apply; ``channels`` is set on ``publisher_news`` only.
    """

    source: str
    first_row_at: datetime | None = None
    last_row_at: datetime | None = None
    last_ingested_at: datetime | None = None
    rows_total: int
    cadence: str = ""
    history_note: str = ""
    limits: list[str] = []
    archive_days: CoverageArchiveDays | None = None
    stale: bool
    stale_after_seconds: int | None = None
    channels: list[CoverageChannel] | None = None


class Coverage(_Base):
    """The whole passport: one :class:`CoverageSource` per data source.

    Computed once a day and served from cache: ``as_of`` is when the counts
    were taken and ``generated_at`` when the payload was assembled, so both
    describe the computation, not the response; rows can be up to a day newer
    than ``last_row_at``. ``research_only`` is always ``True``.
    """

    generated_at: datetime
    as_of: datetime
    research_only: bool = True
    sources: list[CoverageSource]

    def by_source(self, source: str) -> CoverageSource | None:
        """The entry for one source (``"sec_form8k"``…), or ``None`` if absent."""
        return next((s for s in self.sources if s.source == source), None)


__all__ = ["Coverage", "CoverageArchiveDays", "CoverageChannel", "CoverageSource"]
