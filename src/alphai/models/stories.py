"""Story models (``GET /api/stories/*``).

A story is an event that two or more publishers reported, summarised by AlphAI
from the articles themselves. ``story_id`` is the permanent key every article
row carries (``RichNewsArticle.story_id``): the uid of the story's first root
article, unchanged for the story's whole life. Unknown fields are preserved so
a newer API shape never breaks parsing.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)


SummaryState = Literal["published", "stale", "preparing"]
StoryLookupStatus = Literal["found", "merged", "not_a_story"]
TickerImpact = Literal["positive", "negative", "neutral"]


class StoryCard(_Base):
    """A story in a list (top or latest)."""

    story_id: str
    title: str
    summary: str
    # The feed's 1-10 scale: the median of each publisher's best-scored article
    # on the event, rounded down. Listed stories are 7 and above.
    importance: int
    category: str
    tickers: list[str] = []
    # Distinct publishers (always 2 or more) and visible articles (reprints included).
    publishers: int
    materials: int
    first_published_at: datetime | None = None
    last_material_at: datetime | None = None
    # When the key facts last changed — the freshness the top list ranks by.
    updated_at: datetime | None = None
    # ``published``: the summary covers every article the story had when it was
    # written. ``stale``: articles joined since; a rewrite is queued.
    # ``preparing``: no summary yet — title and summary are the lead article's.
    summary_state: SummaryState


class StoryKeyFact(_Base):
    text: str
    # The article the fact was read from (a row of ``materials``); empty when
    # that article has since been removed.
    source_uid: str = ""
    publisher: str = ""


class StoryTickerTake(_Base):
    ticker: str
    # The summary's read of the event for this ticker — an editorial call.
    impact: TickerImpact
    note: str = ""


class Story(StoryCard):
    """The full story: a card plus the summary's body."""

    why_it_matters: str = ""
    key_facts: list[StoryKeyFact] = []
    ticker_takes: list[StoryTickerTake] = []
    uncertainties: list[str] = []
    # "Based on N of M sources": articles whose text the model read, and the
    # story's visible article count when the summary was written.
    based_on: int = 0
    materials_at_build: int = 0
    # Articles that joined after the summary was written (``stale`` only).
    new_materials: int = 0
    revision_generated_at: datetime | None = None
    # Whether alphai.io lets search engines index the story's page. Informational.
    indexable: bool = False


class StoryMaterial(_Base):
    """One article behind a story; open it with ``client.news.get(uid)``."""

    uid: str
    title: str
    publisher: str
    time_published: datetime
    url: str
    relevance_score: int
    seo_eligible: bool = False


class StoryMaterialsPage(_Base):
    story_id: str
    results: list[StoryMaterial]
    # Next (newer) page; ``None`` at the end.
    next_cursor: str | None = None


class StoriesPage(_Base):
    results: list[StoryCard]
    # Next (older) page; ``None`` at the end.
    next_cursor: str | None = None


class TopStories(_Base):
    results: list[StoryCard]
    as_of: datetime
    # The ranking formula's version; a change to the formula increments it.
    ranking_version: int


class StoryArticleRef(_Base):
    """The single-publisher article a non-story id belongs to."""

    uid: str
    title: str
    time_published: datetime


class StoryLookup(_Base):
    """What a story id resolves to.

    ``found``: ``story`` is filled. ``merged``: this story was folded into
    another one, ``redirect_to`` is its id — fetch that one. ``not_a_story``:
    the id belongs to an article only one publisher carried, so there is no
    summary; ``article`` names it. This is the normal answer for most feed
    rows, since most events are carried by a single outlet. An unknown id
    raises ``NotFoundError`` instead.
    """

    status: StoryLookupStatus
    story: Story | None = None
    redirect_to: str | None = None
    article: StoryArticleRef | None = None
