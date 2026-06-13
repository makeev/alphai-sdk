"""Auto-paginate the feed and tally categories.

ALPHAI_API_KEY=ak_live_... python examples/paginate_feed.py
"""

from __future__ import annotations

from collections import Counter

from alphai import Client


def main() -> None:
    counts: Counter[str] = Counter()
    with Client() as client:
        # iter() follows the cursor automatically; max_items caps the walk.
        for article in client.news.iter(min_relevance=6, max_items=200):
            counts[str(article.enrichment.category)] += 1

    print("Category distribution across the latest 200 articles:")
    for category, n in counts.most_common():
        print(f"  {category:<22} {n}")


if __name__ == "__main__":
    main()
