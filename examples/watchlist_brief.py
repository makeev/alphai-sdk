"""A watchlist overview in one call. Run with ALPHAI_API_KEY set."""

import sys

from alphai import Client

with Client() as client:
    brief = client.news.brief(tickers=sys.argv[1:] or ["NVDA", "AMD", "BTC-USD"])
    print(f"Publication window: {brief.window_start} to {brief.window_end}")
    for event in [*brief.events, *brief.filings]:
        print(",".join(event.matched_tickers), event.title, event.article_url)
    for earnings in brief.upcoming_earnings:
        print("Confirmed earnings:", earnings.ticker, earnings.report_date)
    print("Unknown tickers:", brief.unknown_tickers)
    print("Truncated news/filings:", brief.events_truncated, brief.filings_truncated)
