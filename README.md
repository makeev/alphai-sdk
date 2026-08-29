# alphai-sdk

Typed Python client for the [AlphaAI](https://alphai.io) financial-news REST API
— relevance-scored, ticker-linked news and SEC Form 4 insider data, built for AI
agents and trading bots.

- **Sync and async** clients (`Client` / `AsyncClient`) over `httpx`
- **Pydantic v2** response models — autocomplete, validation, `Decimal` money
- **Cursor auto-pagination**, automatic retry on 429/5xx, rate-limit inspection
- **Typed errors** and full coverage of the 11 public endpoints

API reference: <https://api.alphai.io/api/schema/> · Developer guide:
<https://alphai.io/developers>

## Install

```bash
pip install alphai-sdk
```

Requires Python 3.10+. The import name is `alphai`.

## Authentication

Create an API key at <https://alphai.io/account/api-keys>, then pass it
explicitly or via the `ALPHAI_API_KEY` environment variable.

```python
from alphai import Client

# reads $ALPHAI_API_KEY when api_key is omitted
with Client(api_key="ak_live_…") as client:
    page = client.news.list(symbol="NVDA")
    for article in page.results:
        print(article.title, "→", article.relevance_score)
```

Rate limits are per account and two-layer — a per-minute burst plus a per-day
volume cap: **Free 20/min · 100/day · Basic 60/min · 10,000/day · Pro 150/min ·
100,000/day**. News-archive depth is tiered too: Free keys page the feeds back
30 days, Basic 90, Pro 180 (paging past your horizon returns a `403` with an
upgrade hint).

## Quickstart

### List & filter the feed

```python
from alphai import Client, NewsCategory

with Client() as client:
    page = client.news.list(
        symbol="NVDA",
        category=[NewsCategory.EARNINGS, "insider"],  # enum or str; OR-matched
        min_relevance=7,
        collapse_stories=True,  # dedupe syndicated reprints
        page_size=20,  # 10 default; 1-20 on any key, 21-50 needs Pro
    )
    print(page.next_cursor)  # opaque cursor for the next (older) page
    print(page.has_more)
```

### Pull a date window

`from_date` / `to_date` bound the feed to a publication window (inclusive), the
same names the MCP tools use. A `datetime.date` or a bare `YYYY-MM-DD` string
means the whole day, so equal bounds return that day, not an empty page; a
`datetime` is an exact instant (naive is read as UTC):

```python
from datetime import date

with Client() as client:
    july = client.news.list(
        symbol="NVDA",
        from_date=date(2026, 7, 1),
        to_date=date(2026, 7, 31),  # through July 31 23:59:59.999999 UTC
    )
```

The window respects your plan's archive depth (past the horizon is a `403` on
the first page) and applies to the default `sort="published"` mode only — delta
polling never walks back into history, so combining a window with
`sort="ingested"` is a `400`. On `news.insider` the window bounds when the
filing reached the feed, not the trade date inside the `insider` block.

### Poll for what is new (`sort="ingested"`)

Articles reach the feed after their publish time, so a poller that tracks
`time_published` silently skips late arrivals. `sort="ingested"` orders the feed
by arrival instead, and its cursor is a polling position rather than an
end-of-feed marker:

```python
cursor = load_cursor()  # None on the first run

with Client() as client:
    page = client.news.list(
        sort="ingested", cursor=cursor, symbol="NVDA", page_size=20, min_relevance=7
    )
    for article in page.results:
        handle(article)  # article.original.created_at = when we received it
    save_cursor(page.next_cursor)  # always set; empty results = caught up

    # Ask the page, never the cursor: in this mode next_cursor is never null,
    # so `caught_up` (and its inverse `has_more`) is the only honest signal.
    if page.caught_up:
        sleep_until_next_poll()
```

Pass the same `sort` on every call of a run. Each mode mints its own cursor
family, so replaying an ingested cursor into the default mode is a `400`, not a
silent restart. Cursors are opaque: hand one back unchanged, never build one.

**Keep up with the feed.** A delta poll returns one page, so a poller that
drains slower than the feed publishes drifts backwards and its articles read as
hours old — the data is current, the position is not. Raise `page_size` and
narrow the stream (`min_relevance`, `symbol`, `category`) until one poll covers
one interval, and remember the per-day call cap bounds how much of the feed a
plan can drain at all.

On Free and Basic the archive horizon applies to where a poll *resumes*, so a
cursor left unused for longer than your window comes back `403`
(`extra.reason = "archive_horizon"`). Poll on your plan's cadence and you will
not see it; Pro has no window.

### Auto-paginate

`iter()` follows the cursor for you and flattens articles across pages:

```python
with Client() as client:
    for article in client.news.iter(category="earnings", max_items=100):
        print(article.uid, article.title)
```

### Single article, trending, related, insider

```python
with Client() as client:
    client.news.trending()  # top ≤10 from the last 48h
    art = client.news.get("788e477c66f3849b")
    client.news.related(art.uid)  # up to 6 related articles
    client.news.insider(symbol="NVDA")  # SEC Form 4 feed (or .insider_iter())
```

### Symbols & rollups

```python
from decimal import Decimal

with Client() as client:
    client.symbols.list(limit=100)  # active tickers (bare list)
    nvda = client.symbols.get("NVDA")  # detail (404 if unknown)
    btc = client.symbols.get("BTC-USD")  # crypto + foreign listings too
    # Multi-market: .asset_type ("Stock"/"ETF"/"Crypto"), .country, .currency,
    # .supports_insider (US SEC names only). Crypto is "<SYM>-USD"; foreign uses
    # the Yahoo suffix (e.g. "VOD.L").
    sent = client.symbols.sentiment_summary("NVDA")  # 7-day AI sentiment
    ins = client.symbols.insider_summary("NVDA")  # 30-day Form 4 rollup
    assert isinstance(ins.buy_value_usd, Decimal | None)  # money is Decimal
```

### Earnings reads

AlphaAI's own structured read of a company's earnings filings, with every figure
checked against the filing text (8-K item 2.02 for US filers, a 6-K earnings
release for foreign private issuers):

```python
with Client() as client:
    hist = client.symbols.earnings("NVDA")
    print(hist.next_report_date)  # company-confirmed (date | None; never an estimate)
    for read in hist.reports:  # newest first, capped at 20; empty = normal
        a = read.analysis
        print(read.fiscal_period, a.verdict, a.key_metrics[0].value)

    latest = client.symbols.earnings_latest("NVDA")  # pointer for the article link
    article = client.news.get(latest.uid)  # full enrichment
```

`EarningsRead.source_type` distinguishes the filing kind (`sec_form8k` /
`sec_form6k`), and `next_report_date` is `None` whenever AlphaAI holds no
confirmed date — the SDK deliberately does not substitute an estimate.

### Async

Every method mirrors the sync client with `await`; `iter()` is an async generator:

```python
import asyncio
from alphai import AsyncClient


async def main() -> None:
    async with AsyncClient() as client:
        async for article in client.news.iter(symbol="NVDA", max_items=20):
            print(article.title)


asyncio.run(main())
```

## Example projects

- [**alphai-news-to-email**](https://github.com/makeev/alphai-news-to-email) —
  a small, deployable app that emails you a deduplicated digest of high-relevance
  news for your watchlist. Built entirely on this SDK.

## Errors

All errors derive from `AlphaAIError`:

```python
from alphai import Client, RateLimitError, NotFoundError, AuthenticationError

with Client() as client:
    try:
        client.symbols.get("ZZZZ")
    except NotFoundError:
        ...
    except RateLimitError as e:
        print("retry after", e.retry_after, "seconds; limit", e.limit)
    except AuthenticationError:
        ...
```

| Status | Exception |
|--------|-----------|
| 400 | `BadRequestError` (`.fields` for validation errors) |
| 401 | `AuthenticationError` |
| 403 | `PermissionDeniedError` |
| 404 | `NotFoundError` |
| 429 | `RateLimitError` (`.retry_after`, `.limit`, `.remaining`, `.reset`) |
| 5xx | `ServerError` |
| network/timeout | `APIConnectionError` |
| 2xx, unparseable body | `InvalidResponseError` |

GET requests are automatically retried on 429 / 5xx / connection errors
(`max_retries`, default 2) with jittered backoff that honors `Retry-After` (capped
at `max_retry_after`, default 60s, so a bad value can't freeze your process). A
2xx with a non-JSON / empty body raises `InvalidResponseError`.

## Rate-limit budget

Every keyed response carries the `X-RateLimit-*` trio. The last one seen is on
the client:

```python
with Client() as client:
    client.news.list()
    rl = client.last_rate_limit
    if rl:
        print(f"{rl.remaining}/{rl.limit} left, resets at {rl.reset}")
```

## Configuration

```python
Client(
    api_key=None,  # else $ALPHAI_API_KEY
    base_url="https://api.alphai.io",  # API host
    timeout=30.0,
    max_retries=2,  # clamped to >= 0
    backoff_factor=0.5,
    max_retry_after=60.0,  # cap on honored Retry-After (seconds)
    user_agent="alphai-sdk-python/<version>",
    http_client=None,  # bring your own httpx.Client (advanced)
)
```

The same keyword arguments apply to `AsyncClient`. When you pass a custom
`http_client`, the SDK **still applies its `Authorization` header and base URL on
every request** — your client just supplies the transport (proxies, custom
timeout, mounts). You own its lifecycle (the SDK won't close a client you passed in).

## Development

```bash
uv venv && uv pip install -e ".[dev]"
ruff check . && ruff format --check .
mypy src/alphai
pytest                       # offline suite
pytest -m integration        # live tests (needs ALPHAI_API_KEY)
```

## License

MIT — see [LICENSE](LICENSE). API access still requires a valid key.
