"""Minimal sync quickstart.

Run with your key in the environment:

    ALPHAI_API_KEY=ak_live_... python examples/quickstart.py
"""

from __future__ import annotations

from alphai import Client


def main() -> None:
    with Client() as client:  # reads $ALPHAI_API_KEY
        page = client.news.list(symbol="NVDA", min_relevance=7)
        print(f"{len(page.results)} articles (more: {page.has_more})\n")
        for article in page.results:
            print(f"[{article.relevance_score}] {article.title}")
            print(f"    {article.original.source} · {article.original.url}")

        if client.last_rate_limit:
            rl = client.last_rate_limit
            print(f"\nquota: {rl.remaining}/{rl.limit} remaining")


if __name__ == "__main__":
    main()
