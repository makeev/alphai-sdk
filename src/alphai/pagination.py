"""Cursor auto-pagination helpers shared by the sync and async news resources.

Each takes a ``fetch_page`` callable that maps a cursor (``None`` for the first
page) to a :class:`~alphai.models.NewsPagination`, and yields the flattened
articles across pages, stopping at ``max_items`` / ``max_pages`` or when the
feed's ``next_cursor`` is exhausted.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Iterator

from .models import NewsPagination, RichNewsArticle

SyncFetch = Callable[[str | None], NewsPagination]
AsyncFetch = Callable[[str | None], Awaitable[NewsPagination]]


def iterate_pages(
    fetch_page: SyncFetch,
    *,
    max_items: int | None = None,
    max_pages: int | None = None,
) -> Iterator[RichNewsArticle]:
    """Yield articles across pages (synchronous)."""
    count = 0
    pages = 0
    cursor: str | None = None
    while True:
        page = fetch_page(cursor)
        for item in page.results:
            yield item
            count += 1
            if max_items is not None and count >= max_items:
                return
        pages += 1
        if max_pages is not None and pages >= max_pages:
            return
        # Stop when the page itself says it is done. A cursor comparison alone
        # is NOT enough in ingested mode: there `next_cursor` is always set and
        # a caught-up poll parks the position at the GLOBAL feed head, which
        # advances whenever any row is ingested — not just one matching the
        # caller's filter. So an `iter(symbol=…, sort="ingested")` drain that
        # is already caught up kept fetching empty pages whenever a row landed
        # between two calls, burning rate-limit budget on a race. `caught_up`
        # is the mode-aware signal; the cursor check stays as a backstop
        # against a server that repeats a token forever.
        if page.caught_up or page.next_cursor == cursor:
            return
        cursor = page.next_cursor


async def aiterate_pages(
    fetch_page: AsyncFetch,
    *,
    max_items: int | None = None,
    max_pages: int | None = None,
) -> AsyncIterator[RichNewsArticle]:
    """Yield articles across pages (asynchronous)."""
    count = 0
    pages = 0
    cursor: str | None = None
    while True:
        page = await fetch_page(cursor)
        for item in page.results:
            yield item
            count += 1
            if max_items is not None and count >= max_items:
                return
        pages += 1
        if max_pages is not None and pages >= max_pages:
            return
        # Stop when the page itself says it is done. A cursor comparison alone
        # is NOT enough in ingested mode: there `next_cursor` is always set and
        # a caught-up poll parks the position at the GLOBAL feed head, which
        # advances whenever any row is ingested — not just one matching the
        # caller's filter. So an `iter(symbol=…, sort="ingested")` drain that
        # is already caught up kept fetching empty pages whenever a row landed
        # between two calls, burning rate-limit budget on a race. `caught_up`
        # is the mode-aware signal; the cursor check stays as a backstop
        # against a server that repeats a token forever.
        if page.caught_up or page.next_cursor == cursor:
            return
        cursor = page.next_cursor


__all__ = ["AsyncFetch", "SyncFetch", "aiterate_pages", "iterate_pages"]
