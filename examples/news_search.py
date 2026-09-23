"""Search without a ticker. Run with ALPHAI_API_KEY set: python examples/news_search.py."""

from datetime import datetime, timedelta, timezone

from alphai import Client

until = datetime.now(timezone.utc)
since = until - timedelta(days=29)

with Client() as client:
    cursor = None
    for _ in range(2):  # keep this example to at most two API calls
        page = client.news.search(
            query="Jane Street",
            from_date=since,
            to_date=until,
            page_size=20,
            cursor=cursor,
        )
        print(page.query.mode, page.query.note)
        print("Window starts:", page.query.window_from, "Bounded matches:", page.matched)
        for article in page.results:
            print(article.title, article.enrichment.tickers, article.original.url)
            if article.search_match:
                print(article.search_match.context)
        cursor = page.next_cursor
        if not cursor:
            break
