# alphai-sdk

Typed Python client for the [AlphaAI](https://alphai.io) financial-news REST API
— relevance-scored, ticker-linked news and SEC Form 4 insider data, built for AI
agents and trading bots.

- **Sync and async** clients (`Client` / `AsyncClient`) over `httpx`
- **Pydantic v2** response models — autocomplete, validation, `Decimal` money
- **Cursor auto-pagination**, automatic retry on 429/5xx, rate-limit inspection
- **Typed errors** and full coverage of the 9 public endpoints

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

Rate limits are per account, per hour: **Free 100 · Basic 1,000 · Pro 10,000**.

## Quickstart

### List & filter the feed

```python
from alphai import Client, NewsCategory

with Client() as client:
    page = client.news.list(
        symbol="NVDA",
        category=[NewsCategory.EARNINGS, "insider"],   # enum or str; OR-matched
        min_relevance=7,
        collapse_stories=True,                          # dedupe syndicated reprints
    )
    print(page.next_cursor)        # opaque cursor for the next (older) page
    print(page.has_more)
```

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
    client.news.trending()                 # top ≤10 from the last 48h
    art = client.news.get("788e477c66f3849b")
    client.news.related(art.uid)           # up to 6 related articles
    client.news.insider(symbol="NVDA")     # SEC Form 4 feed (or .insider_iter())
```

### Symbols & rollups

```python
from decimal import Decimal

with Client() as client:
    client.symbols.list(limit=100)               # active tickers (bare list)
    nvda = client.symbols.get("NVDA")            # detail (404 if unknown)
    sent = client.symbols.sentiment_summary("NVDA")   # 7-day AI sentiment
    ins = client.symbols.insider_summary("NVDA")      # 30-day Form 4 rollup
    assert isinstance(ins.buy_value_usd, Decimal | None)   # money is Decimal
```

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
    api_key=None,                       # else $ALPHAI_API_KEY
    base_url="https://api.alphai.io",   # API host
    timeout=30.0,
    max_retries=2,                      # clamped to >= 0
    backoff_factor=0.5,
    max_retry_after=60.0,               # cap on honored Retry-After (seconds)
    user_agent="alphai-sdk-python/<version>",
    http_client=None,                   # bring your own httpx.Client (advanced)
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
