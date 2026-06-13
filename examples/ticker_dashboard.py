"""A one-ticker dashboard composing several endpoints.

ALPHAI_API_KEY=ak_live_... python examples/ticker_dashboard.py NVDA
"""

from __future__ import annotations

import sys

from alphai import Client


def dashboard(ticker: str) -> None:
    with Client() as client:
        sym = client.symbols.get(ticker)
        print(f"== {sym.symbol} — {sym.name} ({sym.exchange}) ==")
        print(f"   {sym.sector} / {sym.industry}\n")

        sent = client.symbols.sentiment_summary(ticker)
        print(
            f"7-day sentiment ({sent.total} calls): "
            f"{sent.bullish}▲ / {sent.neutral}● / {sent.bearish}▼"
        )

        ins = client.symbols.insider_summary(ticker)
        print(
            f"30-day insider: {ins.buy_count} buys / {ins.sell_count} sells, "
            f"{ins.pct_10b5_1}% under 10b5-1 plans"
        )
        for insider in ins.top_insiders[:3]:
            print(f"   {insider.name} ({insider.title or 'director'}): net {insider.net_value}")

        print("\nLatest headlines:")
        for article in client.news.iter(symbol=ticker, max_items=5):
            print(f"   [{article.relevance_score}] {article.title}")


def main() -> None:
    ticker = sys.argv[1] if len(sys.argv) > 1 else "NVDA"
    dashboard(ticker.upper())


if __name__ == "__main__":
    main()
