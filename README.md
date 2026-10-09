# alphai-sdk

Typed Python client for the [AlphAI](https://alphai.io) financial-news REST API
— relevance-scored, ticker-linked news and SEC Form 4 insider data, built for AI
agents and trading bots.

- **Sync and async** clients (`Client` / `AsyncClient`) over `httpx`
- **Pydantic v2** response models — autocomplete, validation, `Decimal` money
- **Cursor auto-pagination**, automatic retry on 429/5xx, rate-limit inspection
- **Typed errors**; covers news search, feeds (press and SEC filings), symbols,
  Brief, Radar, the coverage passport and the insider CSV export. Calendar,
  macro and insider-trades are one `Client.request()` call away.

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
        print(article.uid, article.title, article.tickers, article.category)
```

`uid`, `title`, `tickers`, `category` and `relevance_score` are shortcuts into
the `original` / `enrichment` blocks, which keep the full article.

### Single article, trending, related, insider

```python
with Client() as client:
    client.news.trending()  # top ≤10 from the last 48h
    art = client.news.get("788e477c66f3849b")
    client.news.related(art.uid)  # up to 6 related articles
    client.news.insider(symbol="NVDA")  # SEC Form 4 feed (or .insider_iter())
    client.news.insider(symbol="NVDA", is_10b5_1=False)  # discretionary trades only
```

### SEC filings: `source_type`, `item` and the `filing` block

`source_type` picks where rows come from: `gdelt` (press coverage),
`sec_form4`, `sec_form8k` or `sec_form6k`, OR-matched. `item` keeps 8-K filings
that carry an item code anywhere in the filing (`"5.02"` executive changes,
`"1.01"` material agreements, `"8.01"` other events) and implies `sec_form8k`;
next to any other source type it is a `400`. Every 8-K row carries a structured
`filing` block:

```python
with Client() as client:
    page = client.news.list(item="5.02", min_relevance=6)
    for article in page.results:
        filing = article.filing  # EightKFiling | None (None on press, Form 4, 6-K)
        if filing is None:
            continue
        print(article.tickers, filing.items, filing.primary_item, filing.accession_number)
        print(filing.filed_at, filing.event_date, filing.exhibit_url)  # event_date may be None
```

`items` lists every item code in the filing's order and is empty for a filing SEC
served no document for; `primary_item` is the one that set the row's category.
With `collapse_stories=True` an 8-K that carries a press release joins that
release's story, so read filings uncollapsed.

### Insider feed as CSV

`news.insider_csv()` returns the insider feed as one file with the same filters,
walked on the server up to your plan's row cap (Free 500, Basic 2,000, Pro
10,000) inside its archive window. The whole file counts as one request.

```python
import csv
import io

with Client() as client:
    export = client.news.insider_csv(symbol="NVDA", is_10b5_1=False)
    print(export.rows, "rows of", export.row_cap, "->", export.filename)
    for row in csv.DictReader(io.StringIO(export.text)):
        print(row["transaction_date"], row["insider_name"], row["side"], row["total_value_usd"])

    if export.truncated == "row_cap":  # more rows exist: continue from the cursor
        more = client.news.insider_csv(symbol="NVDA", is_10b5_1=False, cursor=export.next_cursor)
```

`truncated` is `"row_cap"`, `"archive_horizon"` (the walk reached your plan's
archive depth) or `None` when the file holds everything the filters select. The
`next_cursor` also works for `news.insider()` with the same `sort`. CSV cells are
strings; parse money with `Decimal` yourself. A bad filter is the same
`BadRequestError` as on the JSON feed, raised before any row.

### Stories

A story is an event that two or more publishers reported, summarised by AlphAI
from the articles themselves: what happened, the figures with the publisher each
came from, why it matters, a read per ticker and the questions the sources leave
open. Every article row carries a permanent `story_id` (the uid of the story's
first root article, unchanged when a stronger copy takes the root over or two
stories merge); a lone article names itself.

```python
with Client() as client:
    top = client.stories.top()  # last 48h, ranked by importance, coverage and freshness
    for card in top.results[:5]:
        print(card.importance, card.publishers, card.title)

    for card in client.stories.iter(max_items=50):  # newest first, across pages
        print(card.last_material_at, card.story_id, card.summary_state)

    # story_id taken from any article row: most resolve to not_a_story
    # (one publisher carried the event), a few to a summarised story.
    lookup = client.stories.get(top.results[0].story_id)
    if lookup.status == "found" and lookup.story is not None:
        story = lookup.story
        print(story.summary, story.why_it_matters)
        for fact in story.key_facts:
            print("-", fact.text, f"({fact.publisher})")
        for take in story.ticker_takes:
            print(take.ticker, take.impact, take.note)
    elif lookup.status == "merged":
        lookup = client.stories.get(lookup.redirect_to)  # or client.stories.get_story(...)
    elif lookup.status == "not_a_story":
        print("single-publisher article:", lookup.article.uid)

    for material in client.stories.iter_materials(top.results[0].story_id):
        print(material.time_published, material.publisher, material.url)
```

`summary_state` is `published`, `stale` (articles joined after the summary; a
rewrite is queued) or `preparing` (no summary yet; `title` and `summary` are the
lead article's). A cursor or a story past your plan's archive horizon raises
`PermissionDeniedError` with `reason == "archive_horizon"`. Summaries are
AI-generated financial information for research, not investment advice; article
bodies are never returned.

### Coverage passport

What each data source holds, from when, and with which caveats. Read it before a
backtest: `first_row_at` is the earliest row we hold, not the start of dense
coverage, and `history_note` says which months are thin.

```python
with Client() as client:
    cov = client.coverage()
    print(cov.as_of)  # computed once a day
    for source in cov.sources:
        print(source.source, source.first_row_at, source.rows_total, source.stale)
    eightk = cov.by_source("sec_form8k")
    if eightk is not None:
        print(eightk.history_note, eightk.limits, eightk.archive_days)
```

### Symbols & rollups

```python
from decimal import Decimal

with Client() as client:
    client.symbols.list(limit=100)  # active tickers (bare list)
    client.symbols.list(search="bitcoin")  # name / brand / prefix lookup → BTC-USD
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

AlphAI's own structured read of a company's earnings filings, with every figure
checked against the filing text (8-K item 2.02 for US filers, a 6-K earnings
release for foreign private issuers):

```python
with Client() as client:
    hist = client.symbols.earnings("NVDA")
    print(hist.next_report_date)  # company-confirmed (date | None; never an estimate)
    for read in hist.reports:  # newest first, capped at 20; empty = normal
        a = read.analysis  # EarningsReport | None
        if a is None or not a.key_metrics:
            continue  # a read can publish without metrics; don't index blindly
        print(read.fiscal_period, a.verdict, a.key_metrics[0].name, a.key_metrics[0].value)

    latest = client.symbols.earnings_latest("NVDA")  # None when no read exists yet (HTTP 204)
    if latest is not None:
        article = client.news.get(latest.uid)  # full enrichment
        read = article.earnings  # EarningsReport | None, even on an earnings article
        if read is not None:
            print(read.verdict, read.headline)
```

`EarningsRead.source_type` distinguishes the filing kind (`sec_form8k` /
`sec_form6k`), and `next_report_date` is `None` whenever AlphAI holds no
confirmed date — the SDK deliberately does not substitute an estimate.

Each `KeyMetric` keeps `value` exactly as the filing printed it and adds
`numeric`, `unit` and `scale` next to it (`"$19,345"` → `19345.0`, `"USD"`,
`"millions"` when the filing's table header says so). `scale` is `None` when
nothing in the filing said it; don't assume millions. Each `Segment` carries
the same three fields for `revenue`, and `EarningsReport.table_scale` names
the unit of the filing's own tables: the notes and `analysis` quote table
figures as printed, so under `"millions"` a bare `$36,197` there is $36,197
million.

### Multi-ticker Brief

```python
from alphai import Client

with Client() as client:
    brief = client.news.brief(tickers=["NVDA", "AMD", "BTC-USD"], hours=24, limit=10)
    for event in [*brief.events, *brief.filings]:
        print(event.matched_tickers, event.title)
    for earnings in brief.upcoming_earnings:
        print(earnings.ticker, earnings.report_date)
    print("Unknown:", brief.unknown_tickers)
    print("More coverage:", brief.events_truncated, brief.filings_truncated)
```

One call covers **1–100 explicit tickers on every tier**. This REST method does
not read your saved account watchlist. `hours` is a publication window (1–168,
default 24); `limit` caps each section independently (1–20, default 20). Events
shared by requested symbols appear once with `matched_tickers`. A missing
confirmed earnings date is left missing.

Brief is a ranked snapshot, with no cursor. Check **both truncation flags**;
narrow the window or use the paginated feed for more coverage. For a complete
incremental alert stream, use `news.list(sort="ingested", ...)` and persist its
cursor. Repeated Brief calls are not a lossless replacement.

### Radar snapshots

```python
from alphai import Client, ConflictError

with Client() as client:
    snapshot = client.radar.snapshot(window="24h", market="us_equity", limit=10)
    print(snapshot.snapshot_id, snapshot.as_of, snapshot.freshness)
    for reading in snapshot.results:
        print(reading.ticker, reading.news_z, reading.sent.value)

    # scope="watchlist" reads the API key owner's existing saved symbols.
    saved = client.radar.snapshot(scope="watchlist")
    print(saved.watchlist_coverage)

    try:
        for reading in client.radar.iter(window="4h", max_items=100):
            print(reading.ticker, reading.stories)
    except ConflictError:
        print("Snapshot expired or context changed. Start a new scan without a cursor.")
```

Filters: `window` (`4h` / `24h`), `scope`, `market`, exact `ticker` or `tickers`,
`search`, `sort`, `order`, `sentiment`, `min_z`, `limit`, `offset`, `cursor`.
Ticker filters do not expand aliases. `limit` is page size (1–100, default 50),
not a tier ticker cap; an explicitly empty ticker list is rejected.

The server delays the **whole snapshot**: Free 60 minutes, Basic 15, Pro no added
delay. Check `as_of`, `access` and `freshness`; processing adds latency. Scores and
sentiment may be `None`; keep them missing. Radar describes news activity and is
not a confirmed trading signal or a point-in-time backtest.

For manual pagination, pass `next_cursor` as `cursor` with the **same filters and
limit**. Cursors pin immutable snapshots, retained for three hours. HTTP 409 raises
`ConflictError` when the snapshot/context expires or changes; start a new scan
without a cursor. Iteration never silently restarts. HTTP 503 raises `ServerError`
after bounded retries when no eligible snapshot is available. An empty saved
watchlist returns an empty result.

Runnable examples: [watchlist brief](examples/watchlist_brief.py) and
[Radar](examples/radar.py). Both methods also work with `AsyncClient`; the Radar
iterator is an async generator.

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
- [**alphai-earnings-week**](https://github.com/makeev/alphai-earnings-week) —
  one markdown card per week for a watchlist: confirmed next report dates, the
  latest filing-verified read per name, and the week's macro calendar, in 26
  calls on the Free tier. Write-up with every response of the run:
  [Earnings week from the filings, not the headlines](https://dev.to/makeev/earnings-week-from-the-filings-not-the-headlines-one-script-on-a-free-api-key-l5d).

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
| 400 | `BadRequestError` (`.fields` for validation errors; `.allowed_params` lists the endpoint's real parameter names when you sent an unknown one) |
| 401 | `AuthenticationError` |
| 403 | `PermissionDeniedError` |
| 404 | `NotFoundError` |
| 409 | `ConflictError` (restart a new Radar scan without a cursor) |
| 429 | `RateLimitError` (`.retry_after`, `.limit`, `.remaining`, `.reset`) |
| 5xx | `ServerError` |
| network/timeout | `APIConnectionError` |
| 2xx, unparseable body | `InvalidResponseError` |

GET requests are automatically retried on 429 / 5xx / connection errors
(`max_retries`, default 2) with jittered backoff that honors `Retry-After` (capped
at `max_retry_after`, default 60s, so a bad value can't freeze your process). A
2xx with a non-JSON / empty body raises `InvalidResponseError`.

Every wait before a retry is logged at `WARNING` on the `alphai` logger, so a
client sleeping on a 429 never looks hung. With no logging configured, Python
prints it to stderr:

```text
alphai: HTTP 429 (rate limited) on GET /api/news/; waiting 12.0s before retry 1 of 2 (Retry-After: 12s; daily budget 87/100 left)
```

Route it like any logger, or silence it with
`logging.getLogger("alphai").setLevel(logging.ERROR)`.

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

The trio reports the **per-day** layer. The per-minute burst cap is not in any
header: it shows up only as a 429 with a short `Retry-After`, which the client
waits out (and logs). A 429 while the daily budget still has room is the
per-minute cap; pace bursts yourself if you need to avoid it.

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

## Search by name or phrase

```python
from datetime import datetime, timedelta, timezone

from alphai import Client

until = datetime.now(timezone.utc)
since = until - timedelta(days=29)  # inside the Free archive window

with Client() as client:
    page = client.news.search(query="Jane Street", from_date=since, to_date=until, page_size=20)
    print(page.query.mode, page.query.note, page.matched)
    for article in page.results:
        print(article.title, article.enrichment.tickers)
        if article.search_match:
            print(article.search_match.context)

    if page.next_cursor:
        next_page = client.news.search(
            query="Jane Street",
            from_date=since,
            to_date=until,
            page_size=20,
            cursor=page.next_cursor,
        )
```

`news.search()` is also available on `AsyncClient` with `await`. It returns a
`NewsSearchPage`, including typed `query` interpretation and per-article
`search_match` details. Quoted phrases such as `query='"going concern"'`,
`-word` exclusions and `OR` are passed through unchanged. Add `symbol`,
`category`, `source_type`, `item`, `min_relevance` or `collapse_stories` to narrow
results. `item="5.02"` limits search to 8-Ks carrying that item. Dates accept ISO
strings, `date` or `datetime`, with the same semantics as the news feed.

Inspect `query.mode` and `query.note`: `broadened` can match only some words;
`no_match` and `no_terms` are empty answers within the searched coverage, not
proof an event did not happen. `matched` counts visible candidates among the best
200, not all articles in the archive. `count` is the current page size. Context
can be `None` for matches in titles/entity names; scores compare only within a
response. To continue, reuse the query, filters and window with `next_cursor`.
Invalid cursors raise `BadRequestError`; search downtime raises `ServerError`
(after the configured retries), never a successful empty page.

Runnable example: [news search](examples/news_search.py). Try the same queries
in [AlphAI Search](https://alphai.io/search).

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
