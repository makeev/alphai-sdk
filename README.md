# alphai-sdk

Typed Python client for the [AlphaAI](https://alphai.io) financial-news REST API
— relevance-scored, ticker-linked news and SEC Form 4 insider data for AI agents
and trading bots.

> Status: in development. API reference: <https://api.alphai.io/api/schema/> ·
> Developer guide: <https://alphai.io/developers>

## Install

```bash
pip install alphai-sdk
```

The import name is `alphai`:

```python
import alphai
```

## Authentication

Create an API key at <https://alphai.io/account/api-keys> and pass it explicitly
or via the `ALPHAI_API_KEY` environment variable.

```python
from alphai import Client

with Client(api_key="ak_live_…") as client:   # or: Client()  -> reads $ALPHAI_API_KEY
    page = client.news.list(symbol="NVDA")
    for article in page.results:
        print(article.original.title, article.enrichment.relevance_score)
```

Async mirror:

```python
import asyncio
from alphai import AsyncClient

async def main() -> None:
    async with AsyncClient() as client:
        page = await client.news.list(symbol="NVDA")
        print(len(page.results), page.next_cursor)

asyncio.run(main())
```

## What's covered

The SDK wraps the 9 public REST endpoints 1:1:

- **News** — `news.list`, `news.iter` (auto-pagination), `news.trending`,
  `news.insider`, `news.insider_iter`, `news.get(uid)`, `news.related(uid)`.
- **Symbols** — `symbols.list`, `symbols.get`, `symbols.sentiment_summary`,
  `symbols.insider_summary`.

Rate limits are per account, per hour: Free 100 / Basic 1,000 / Pro 10,000.

## License

MIT — see [LICENSE](LICENSE). API access still requires a valid key.
