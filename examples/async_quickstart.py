"""Minimal async quickstart.

ALPHAI_API_KEY=ak_live_... python examples/async_quickstart.py
"""

from __future__ import annotations

import asyncio

from alphai import AsyncClient


async def main() -> None:
    async with AsyncClient() as client:  # reads $ALPHAI_API_KEY
        trending = await client.news.trending()
        print(f"{len(trending)} trending stories:")
        for article in trending:
            print(f"  [{article.relevance_score}] {article.title}")

        print("\nlatest NVDA (async iter):")
        async for article in client.news.iter(symbol="NVDA", max_items=5):
            print(f"  {article.uid} {article.title}")


if __name__ == "__main__":
    asyncio.run(main())
