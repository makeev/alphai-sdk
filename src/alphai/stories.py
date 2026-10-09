"""Stories: events covered by two or more publishers, summarised from their sources.

``client.stories.top()`` ranks the last 48 hours, ``client.stories.list()`` pages
every story newest-first, ``client.stories.get(story_id)`` resolves a story id
(the ``story_id`` every article row carries) and ``client.stories.materials()``
lists the articles behind one. Same tier rules as the news feeds: a cursor or a
story past the key's archive horizon raises ``PermissionDeniedError`` (``archive_horizon``).
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator
from typing import TYPE_CHECKING, Any

from ._requests import _path_segment
from .models.stories import (
    StoriesPage,
    Story,
    StoryCard,
    StoryLookup,
    StoryMaterial,
    StoryMaterialsPage,
    TopStories,
)

if TYPE_CHECKING:
    from .async_client import AsyncClient
    from .client import Client

STORIES = "/api/stories/"
STORIES_TOP = "/api/stories/top/"


def story_detail_path(story_id: str) -> str:
    return f"/api/stories/{_path_segment(story_id, 'story_id')}/"


def story_materials_path(story_id: str) -> str:
    return f"/api/stories/{_path_segment(story_id, 'story_id')}/materials/"


def build_page_params(*, cursor: str | None, page_size: int | None) -> dict[str, Any]:
    if page_size is not None and not 1 <= page_size <= 50:
        raise ValueError("page_size must be between 1 and 50")
    return {"cursor": cursor, "page_size": page_size}


class StoriesResource:
    """Story endpoints (``/api/stories/*``)."""

    def __init__(self, client: Client) -> None:
        self._client = client

    def top(self) -> TopStories:
        """The strongest stories of the last 48 hours, ranked: importance plus a
        coverage bonus, minus one point per 12 hours since the facts last
        changed; one slot per ticker. Up to 50, no pagination."""
        return TopStories.model_validate(self._client.request("GET", STORIES_TOP))

    def list(self, *, cursor: str | None = None, page_size: int | None = None) -> StoriesPage:
        """One page of stories newest-first by their latest article (default 20,
        ``page_size`` 1-50 on every tier). Pass ``next_cursor`` back as
        ``cursor``; paging past the key's archive horizon raises
        ``PermissionDeniedError`` (reason ``archive_horizon``)."""
        params = build_page_params(cursor=cursor, page_size=page_size)
        return StoriesPage.model_validate(self._client.request("GET", STORIES, params))

    def iter(
        self,
        *,
        page_size: int | None = None,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> Iterator[StoryCard]:
        """Auto-paginate :meth:`list`, newest first."""
        cursor: str | None = None
        count = pages = 0
        while True:
            page = self.list(cursor=cursor, page_size=page_size)
            for card in page.results:
                yield card
                count += 1
                if max_items is not None and count >= max_items:
                    return
            pages += 1
            if page.next_cursor is None or (max_pages is not None and pages >= max_pages):
                return
            cursor = page.next_cursor

    def get(self, story_id: str) -> StoryLookup:
        """Resolve a story id — the ``story_id`` of any article row, or an id
        from :meth:`top` / :meth:`list`. Read ``status`` first: ``found``
        carries the story, ``merged`` names the surviving story in
        ``redirect_to``, ``not_a_story`` means one publisher carried the event
        and ``article`` names the row. An unknown id raises ``NotFoundError``;
        a story older than the key's archive horizon raises
        ``PermissionDeniedError`` (reason ``archive_horizon``)."""
        return StoryLookup.model_validate(self._client.request("GET", story_detail_path(story_id)))

    def get_story(self, story_id: str, *, follow_merges: int = 3) -> Story | None:
        """The story itself, following ``merged`` redirects (at most
        ``follow_merges`` hops); ``None`` when the id is ``not_a_story``."""
        lookup = self.get(story_id)
        hops = 0
        while lookup.status == "merged" and lookup.redirect_to and hops < follow_merges:
            lookup = self.get(lookup.redirect_to)
            hops += 1
        return lookup.story

    def materials(
        self, story_id: str, *, cursor: str | None = None, page_size: int | None = None
    ) -> StoryMaterialsPage:
        """The articles behind a story, oldest first (default 50 per page). Only a
        current story has materials: a merged or single-publisher id raises
        ``NotFoundError`` — resolve it with :meth:`get` first."""
        params = build_page_params(cursor=cursor, page_size=page_size)
        data = self._client.request("GET", story_materials_path(story_id), params)
        return StoryMaterialsPage.model_validate(data)

    def iter_materials(
        self, story_id: str, *, page_size: int | None = None
    ) -> Iterator[StoryMaterial]:
        """Every article behind a story, oldest first, across pages."""
        cursor: str | None = None
        while True:
            page = self.materials(story_id, cursor=cursor, page_size=page_size)
            yield from page.results
            if page.next_cursor is None:
                return
            cursor = page.next_cursor


class AsyncStoriesResource:
    """Async story endpoints — see :class:`StoriesResource` for the semantics."""

    def __init__(self, client: AsyncClient) -> None:
        self._client = client

    async def top(self) -> TopStories:
        return TopStories.model_validate(await self._client.request("GET", STORIES_TOP))

    async def list(self, *, cursor: str | None = None, page_size: int | None = None) -> StoriesPage:
        params = build_page_params(cursor=cursor, page_size=page_size)
        return StoriesPage.model_validate(await self._client.request("GET", STORIES, params))

    async def iter(
        self,
        *,
        page_size: int | None = None,
        max_items: int | None = None,
        max_pages: int | None = None,
    ) -> AsyncIterator[StoryCard]:
        cursor: str | None = None
        count = pages = 0
        while True:
            page = await self.list(cursor=cursor, page_size=page_size)
            for card in page.results:
                yield card
                count += 1
                if max_items is not None and count >= max_items:
                    return
            pages += 1
            if page.next_cursor is None or (max_pages is not None and pages >= max_pages):
                return
            cursor = page.next_cursor

    async def get(self, story_id: str) -> StoryLookup:
        data = await self._client.request("GET", story_detail_path(story_id))
        return StoryLookup.model_validate(data)

    async def get_story(self, story_id: str, *, follow_merges: int = 3) -> Story | None:
        lookup = await self.get(story_id)
        hops = 0
        while lookup.status == "merged" and lookup.redirect_to and hops < follow_merges:
            lookup = await self.get(lookup.redirect_to)
            hops += 1
        return lookup.story

    async def materials(
        self, story_id: str, *, cursor: str | None = None, page_size: int | None = None
    ) -> StoryMaterialsPage:
        params = build_page_params(cursor=cursor, page_size=page_size)
        data = await self._client.request("GET", story_materials_path(story_id), params)
        return StoryMaterialsPage.model_validate(data)

    async def iter_materials(
        self, story_id: str, *, page_size: int | None = None
    ) -> AsyncIterator[StoryMaterial]:
        cursor: str | None = None
        while True:
            page = await self.materials(story_id, cursor=cursor, page_size=page_size)
            for material in page.results:
                yield material
            if page.next_cursor is None:
                return
            cursor = page.next_cursor


__all__ = ["AsyncStoriesResource", "StoriesResource"]
