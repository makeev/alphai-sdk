"""Triage a watchlist: which names have something going on this week?

Three questions per ticker, all asked concurrently:

- how did the last 7 days of news coverage lean?
- did insiders buy or sell in the last 30 days?
- is an earnings date confirmed?

Each ticker costs three calls, so a five-name list is 15 calls and fits the
free tier (20 requests/minute, 100/day).

ALPHAI_API_KEY=ak_live_... python examples/watchlist_triage.py NVDA AMD TSM AVGO MU
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass
from datetime import date

from alphai import AsyncClient

DEFAULT_WATCHLIST = ["NVDA", "AMD", "TSM", "AVGO", "MU"]


@dataclass
class Row:
    ticker: str
    calls: int  # articles analysed in the last 7 days
    lean: float  # (bullish - bearish) / total, from -1 to +1
    buys: int
    sells: int
    next_report: date | None  # company-confirmed only, never an estimate


async def triage(client: AsyncClient, ticker: str) -> Row:
    sentiment, insider, earnings = await asyncio.gather(
        client.symbols.sentiment_summary(ticker),
        client.symbols.insider_summary(ticker),
        client.symbols.earnings(ticker),
    )
    total = sentiment.total
    lean = (sentiment.bullish - sentiment.bearish) / total if total else 0.0
    return Row(
        ticker=ticker,
        calls=total,
        lean=lean,
        buys=insider.buy_count,
        sells=insider.sell_count,
        next_report=earnings.next_report_date,
    )


async def main(watchlist: list[str]) -> None:
    async with AsyncClient() as client:
        rows = await asyncio.gather(*(triage(client, t) for t in watchlist))

    # Strongest lean first, in either direction.
    rows.sort(key=lambda r: abs(r.lean), reverse=True)

    print(f"{'ticker':<7}{'7d calls':>9}{'lean':>7}{'30d buy/sell':>14}  next report")
    for r in rows:
        print(
            f"{r.ticker:<7}{r.calls:>9}{r.lean:>+7.2f}"
            f"{r.buys:>7}/{r.sells:<6}  {r.next_report or '-'}"
        )


if __name__ == "__main__":
    tickers = [t.upper() for t in sys.argv[1:]] or DEFAULT_WATCHLIST
    asyncio.run(main(tickers))
