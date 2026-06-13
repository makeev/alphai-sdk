# Plan — `alphai-sdk`: Python SDK for the AlphaAI public REST API

> This document is **self-contained**. It will be copied into the new repo as
> `alphai-sdk/PLAN.md` so all work can happen in that directory **without
> needing the `alphai_io` backend checkout**. Everything an implementer needs —
> the full public API contract, the package design, and the build/release plan —
> is embedded below.

---

## Context

AlphaAI ships a paid, key-authenticated public REST API (`api.alphai.io`,
OpenAPI **1.5.0**) serving relevance-scored, ticker-linked financial news +
SEC Form 4 insider data. Today consumers hand-roll `requests`/`httpx` calls,
re-implement cursor pagination, mis-parse the money-as-decimal-string fields,
and have no typed models. A first-party Python SDK lowers the integration cost
for the exact audience the product targets — "financial news for AI agents and
trading bots" — and is a distribution lever (PyPI listing, `pip install
alphai-sdk` in docs, examples on `/developers`).

**Goal:** a typed, ergonomic, well-tested Python client that wraps the 9 public
REST endpoints 1:1, handles auth / pagination / retries / rate-limit headers /
the error envelope correctly, and is publishable to PyPI.

**Decisions locked with the user:**
- Client style: **both sync (`Client`) and async (`AsyncClient`)**, shared core.
- Models: **Pydantic v2** (validation, `Decimal` coercion, enums, autocomplete).
- Distribution name: **`alphai-sdk`** on PyPI; **import name stays `alphai`**.
- License: **MIT**.

**Scope guardrails:**
- The SDK wraps **only the 9 documented REST endpoints** (below). It must **not**
  invent endpoints that exist only as MCP tools backed by direct DB reads —
  notably there is **no REST full-text `q` search**, no `actionable_now`, no
  `pair_analysis` endpoint. Convenience helpers may *compose* real endpoints
  (e.g. a ticker dashboard that calls sentiment + insider summaries), but must
  not imply server features that aren't there.
- API-key **management** (create/revoke) is JWT-only via the website
  (`/account/api-keys`) — **out of scope**. The SDK only *consumes* a key.
- `raw_text` is never exposed by the API — the SDK models must not include it.

---

## Part A — The public API contract (source of truth for the models)

Authoritative source: the hand-written `backend/openapi.yaml` v1.5.0, served at
`GET /api/schema/`. Reproduced here so the SDK can be built standalone.

### Hosts & auth
- Base URL (default): `https://api.alphai.io` — **key required** on every route
  except `/api/schema/` and `/api/telegram/webhook/`.
- Alt base URL: `https://alphai.io` — same routes also answer (behind edge
  anti-bot; no rate guarantees). SDK default should be `api.alphai.io`.
- Auth header: `Authorization: Bearer ak_live_<random>`. Key issued from
  `/account/api-keys` on the website.
- Rate limits (per account, hourly, sliding window): **Free 100 / Basic 1000 /
  Pro 10000** requests/hour.
- Every keyed response carries: `X-RateLimit-Limit`, `X-RateLimit-Remaining`,
  `X-RateLimit-Reset` (epoch secs of next bucket). On **429** also `Retry-After`
  (seconds). Cache-served responses may omit the trio.

### Error envelope (must handle BOTH shapes)
- **DRF custom handler** (`apps/main/exceptions.py`) → most errors
  (400/401/403/404/429): `{"message": "...", "extra": {...}}`. For validation
  400s, `extra = {"fields": {<field>: [msgs]}}`.
- **Host-gate middleware** (fires before DRF, on missing key) →
  `{"detail": "API key required."}`.
- The openapi `Error` schema loosely lists `message` / `error` / `detail` — the
  SDK's error parser should read `message` first, then fall back to `detail`,
  then the raw body. Never assume a single key.

### The 9 endpoints

| # | Method & path | Purpose | Key params | Returns |
|---|---|---|---|---|
| 1 | `GET /api/news/` | Main feed, newest first; default `relevance_score≥6` + ≥1 ticker | `cursor`, `symbol`, `category[]`, `exclude_categories[]`, `min_relevance` (1–10, default 6), `collapse=story` | `NewsPagination` |
| 2 | `GET /api/news/trending/` | Last 48h, `score≥8`, ranked, reprints collapsed | — (fixed 10, no pagination) | `RichNewsArticle[]` |
| 3 | `GET /api/news/insider/` | `category=insider` feed (Form 4 + 13F press) | `cursor`, `symbol` | `NewsPagination` |
| 4 | `GET /api/news/{uid}/` | Single article (`uid` = `^[a-f0-9]{16}$`) | — | `RichNewsArticle` |
| 5 | `GET /api/news/{uid}/related/` | ≤6 related articles | — | `{ "results": RichNewsArticle[] }` |
| 6 | `GET /api/symbols/` | All active tickers, alphabetical (~10k) | `limit` (1–10000), `offset` (≥0) | `Symbol[]` (bare array) |
| 7 | `GET /api/symbols/{ticker}/` | Symbol detail (`ticker` = `^[A-Z][A-Z0-9.\-]{0,9}$`) | — | `Symbol` |
| 8 | `GET /api/symbols/{ticker}/sentiment-summary/` | 7-day AI sentiment rollup (excludes Form 4) | — | `TickerSentimentSummary` |
| 9 | `GET /api/symbols/{ticker}/insider-summary/` | 30-day Form 4 rollup | — | `TickerInsiderSummary` |

**Param encoding notes:**
- `category` / `exclude_categories`: accept a single value, a CSV string, or a
  repeated param (OR semantics). SDK should accept `str | NewsCategory |
  list[...]` and serialize as repeated query params (`?category=a&category=b`).
- `collapse`: only `"story"` is valid; anything else → 400. When set, items get
  non-null `story_id`, `sources_count`, `sources`.
- Cursors are **opaque** — never build/parse; an invalid cursor → 400.
- Unknown but well-formed ticker on endpoints 8/9 → **zeros, not 404**.
  Endpoint 7 → 404 for unknown ticker.

### Response shapes (→ Pydantic models)

**`RichNewsArticle`** (endpoints 1–5):
```
original: OriginalArticle
enrichment: EnrichedArticle
story_id:      str | None        # collapse=story only
sources_count: int | None        # collapse=story only
sources:       list[str] | None  # collapse=story only, ≤10 domains
```
**`OriginalArticle`** (`raw_text` intentionally absent):
```
id: int | None; uid: str; title: str; url: str(uri)
time_published: datetime; authors: list[str]; summary: str
banner_image: str|None; source: str; source_domain: str
topics: list[Topic]                       # {topic:str, relevance:float}
tickers_sentiment: list[dict]             # loose; model permissively (see note)
created_at: datetime; updated_at: datetime
```
**`EnrichedArticle`**:
```
category: NewsCategory
tickers: list[str]                        # validated, live column
relevance_score: int (1–10)
ai_trading_insights: AITradingInsights
news_context_enhancement: NewsContextEnhancement
```
**`AITradingInsights`**: `ticker_analysis: list[TickerAnalysis]`,
`news_trading_value: NewsTradingValue`, `indirect_market_effects:
IndirectMarketEffects`, `alternative_perspectives: AlternativePerspectives`.
- **`TickerAnalysis`**: `ticker`, `relevance_context`, `impact_analysis:
  ImpactAnalysis`.
- **`ImpactAnalysis`**: `summary`, `sentiment: Sentiment`,
  `price_impact_prediction`, `confidence: Confidence`, `reasoning`.
- **`NewsTradingValue`**: `actionability_score: Actionability`,
  `information_novelty: int (0–10)`, `timing_relevance`,
  `market_sentiment_alignment`, `estimated_read_time: str`.
- **`IndirectMarketEffects`**: `sector_implications`, `regional_market_impact`,
  `global_market_relevance`.
- **`AlternativePerspectives`**: `contrarian_view`, `overlooked_factors`.

**`NewsContextEnhancement`**: `background_context`, `impact_analysis`,
`key_entities: list[KeyEntity{name,type,description}]`,
`market_relevance_summary`, `estimated_read_time_minutes: int`.

**`NewsPagination`** (endpoints 1, 3): `results: list[RichNewsArticle]`,
`next_cursor: str | None`.

**`Symbol`** (endpoints 6, 7): `symbol`, `name`, `asset_type` (Stock|ETF),
`exchange` (NYSE/NASDAQ/AMEX/OTC/CBOE, "" if unknown), `sector`, `industry`,
`description`, `website: str|None`. (List endpoint omits description/website in
practice; model them as optional.)

**`TickerSentimentSummary`** (endpoint 8): `ticker`, `days` (7), `total`,
`bullish`, `neutral`, `bearish`, `daily: list[DailySentimentBucket{day:date,
bullish, neutral, bearish}]`.

**`TickerInsiderSummary`** (endpoint 9): `ticker`, `days` (30),
`total_transactions`, `buy_count`, `sell_count`,
**`buy_value_usd: Decimal | None`**, **`sell_value_usd: Decimal | None`**,
`pct_10b5_1: int (0–100)`,
`top_insiders: list[TopInsider{name, title, transaction_count,
net_value: Decimal | None}]`.
→ **Money fields are decimal strings in JSON; Pydantic must coerce to `Decimal`.**

### Enums
- **`NewsCategory`** (14): `earnings, mergers_acquisitions, regulation,
  macro_economy, sector_analysis, market_movers, technology, commodities,
  crypto, ipo, geopolitics, insider, corporate_actions, other`.
- **`Sentiment`**: `positive, neutral, negative`.
- **`Confidence`**: `high, medium, low`.
- **`Actionability`**: `high, medium, low, negligible`.

**Forward-compat:** set response models to `model_config =
ConfigDict(extra="allow")` and make enum-typed fields tolerant (e.g. parse
unknown category strings without raising — use a validator that falls back to
keeping the raw string) so a future API field/category doesn't break old SDKs.
Model `tickers_sentiment` loosely as `list[dict[str, Any]]` (openapi declares it
`additionalProperties: true`).

---

## Part B — SDK design

### Package layout (`src/` layout, import name `alphai`)
```
alphai-sdk/
├── pyproject.toml            # hatchling build backend, PEP 621 metadata
├── README.md  LICENSE(MIT)  CHANGELOG.md  PLAN.md  .gitignore  .python-version
├── .github/workflows/ci.yml
├── src/alphai/
│   ├── __init__.py           # re-exports Client, AsyncClient, models, errors, __version__
│   ├── _version.py           # __version__ = "0.1.0"
│   ├── _config.py            # ClientConfig: base_url, api_key, timeout, max_retries, backoff
│   ├── _core.py              # shared: header build, query encoding, retry policy, RateLimit, response→model/error parsing (pure, transport-agnostic)
│   ├── _requests.py          # pure request builders per endpoint: (method, path, params) + the model to parse into
│   ├── client.py             # Client (sync, httpx.Client) + sync resources
│   ├── async_client.py       # AsyncClient (httpx.AsyncClient) + async resources
│   ├── errors.py             # exception hierarchy
│   ├── pagination.py         # NewsPage helpers + cursor iterators (sync gen + async gen)
│   ├── models/
│   │   ├── __init__.py
│   │   ├── enums.py          # NewsCategory, Sentiment, Confidence, Actionability
│   │   ├── news.py           # RichNewsArticle + all nested + NewsPagination
│   │   └── symbols.py        # Symbol, TickerSentimentSummary, TickerInsiderSummary, ...
│   └── py.typed              # PEP 561 marker (ship types)
├── tests/                    # pytest + pytest-asyncio + respx; fixtures/ holds captured JSON
└── examples/                 # quickstart.py, paginate_feed.py, ticker_dashboard.py
```

### Sync/async dedup strategy
Keep duplication low by isolating all I/O-free logic:
- **`_requests.py`** — pure functions returning `(method, path, params, ModelType)`
  for each endpoint (e.g. `news_list(symbol, category, …)`).
- **`_core.py`** — pure helpers: `build_headers(api_key)`, `encode_params(...)`
  (repeated-param arrays, drop `None`), `parse_response(status, headers, body,
  ModelType) -> model | raises`, `RateLimit.from_headers(...)`,
  `compute_backoff(attempt, retry_after)`.
- **`client.py` / `async_client.py`** — each owns only the thin transport loop
  (`_request` with the retry/sleep) and resource wrappers. Sync uses
  `time.sleep`; async uses `asyncio.sleep`. Both call the same `_requests` +
  `_core` functions, so models, params, and error mapping live in one place.

### Public surface
```python
from alphai import Client, AsyncClient

c = Client(api_key="ak_live_…")          # or env ALPHAI_API_KEY; base_url overridable
# resources:
c.news.list(symbol="NVDA", category=["earnings","insider"],
            exclude_categories=None, min_relevance=6, collapse="story",
            cursor=None) -> NewsPage
c.news.iter(symbol="NVDA", max_items=100) -> Iterator[RichNewsArticle]  # auto-cursor
c.news.trending() -> list[RichNewsArticle]
c.news.insider(symbol="NVDA", cursor=None) -> NewsPage
c.news.insider_iter(symbol="NVDA") -> Iterator[RichNewsArticle]
c.news.get(uid) -> RichNewsArticle
c.news.related(uid) -> list[RichNewsArticle]
c.symbols.list(limit=None, offset=0) -> list[Symbol]
c.symbols.get(ticker) -> Symbol
c.symbols.sentiment_summary(ticker) -> TickerSentimentSummary
c.symbols.insider_summary(ticker) -> TickerInsiderSummary
c.last_rate_limit -> RateLimit | None     # updated after each call

# context-manager closes the httpx client:
with Client() as c: ...
# AsyncClient mirrors all of the above with `await` and `aiter`/`insider_aiter`.
```
- `NewsPage`: `results: list[RichNewsArticle]`, `next_cursor: str | None`, plus
  `has_more` property. `iter()` loops pages until `next_cursor is None`, honoring
  optional `max_items` / `max_pages`.

### Errors (`errors.py`)
```
AlphaAIError                       # base; carries .status, .message, .body, .request_id?
├── APIConnectionError             # network/timeout (wraps httpx errors)
├── APIStatusError                 # any non-2xx; .status, .message, .extra
│   ├── BadRequestError    (400)   # .fields for validation
│   ├── AuthenticationError(401)
│   ├── PermissionDeniedError(403)
│   ├── NotFoundError      (404)
│   ├── RateLimitError     (429)   # .retry_after, .limit, .remaining, .reset
│   └── ServerError        (>=500)
```
`parse_response` maps status→exception, reading `message` then `detail`.

### Retry policy
httpx retries only connection errors at the transport layer; status-based retry
is implemented in the `_request` loop: retry on **429** and **5xx** up to
`max_retries` (default 2), exponential backoff with full jitter, and on 429
**respect `Retry-After`** when present. `GET`-only API → all calls are
idempotent, safe to retry. Configurable/disable via `ClientConfig`.

### Config & defaults
`base_url="https://api.alphai.io"`, `api_key` from arg or `$ALPHAI_API_KEY`
(raise a clear error if missing), `timeout=30.0`, `max_retries=2`,
`user_agent="alphai-python/<version>"`. Allow passing a custom `httpx.Client`/
`AsyncClient` for advanced users (proxies, custom transport for tests).

---

## Part C — Tooling, tests, packaging

- **Build:** `hatchling`, PEP 621 metadata in `pyproject.toml`, dynamic version
  from `alphai._version.__version__`. Python **3.10+** (uses `X | None`).
- **Runtime deps:** `httpx>=0.27`, `pydantic>=2.7`.
- **Dev deps:** `pytest`, `pytest-asyncio`, `respx` (httpx mocking), `ruff`,
  `mypy`. (This is a *new* repo — the backend's "no respx/factory_boy" rule does
  **not** apply here; choose the best tools for an httpx SDK.)
- **Lint/format:** `ruff` (lint + format). **Types:** `mypy --strict` over
  `src/alphai`; ship `py.typed`.
- **Tests** (offline, deterministic — respx intercepts httpx, fixtures hold
  captured JSON):
  - `test_news.py` / `test_symbols.py` — each endpoint parses a captured
    response into the right model; assert key fields incl. `Decimal` money and
    `NewsCategory` enum.
  - `test_pagination.py` — `iter()` follows `next_cursor` across 2 pages and
    stops on `null`; `max_items` cap; async `aiter` parity.
  - `test_errors.py` — 401 `{detail}`, 401 `{message}`, 400 validation
    `{message, extra.fields}`, 404, 429 (asserts `retry_after`/`limit` parsed),
    500.
  - `test_retry.py` — 429-then-200 retries and honors `Retry-After`; 500-then-200;
    gives up after `max_retries`.
  - `test_params.py` — `category` list → repeated params; `None` dropped;
    `collapse`/`min_relevance` passthrough.
  - Async coverage via `pytest-asyncio` for the `AsyncClient` mirror.
  - **Capture fixtures** from a real prod key (the smoke-test key or a dev Free
    key) once during execution; sanitize and commit under `tests/fixtures/`.
  - **Optional integration test** (`-m integration`, skipped without
    `$ALPHAI_API_KEY`): hit live `api.alphai.io` for one news page + one symbol +
    one summary; a thin guard against contract drift. CI runs it nightly if a key
    secret exists.
- **CI** (`.github/workflows/ci.yml`): matrix Python 3.10–3.13 → ruff, mypy,
  pytest (offline). Separate optional job for the integration/drift test.
- **Docs:** `README.md` with install, auth (env var), quickstart (sync+async),
  pagination, error handling, rate-limit inspection, tier limits, link to
  `/developers` + `/api/schema/`. `examples/` runnable scripts. `CHANGELOG.md`
  (Keep a Changelog format), starting at `0.1.0`.

---

## Part D — Release / distribution (the "deployment" section)

The SDK's analogue of a deploy is a PyPI publish:
1. **Pre-publish:** confirm the name `alphai-sdk` is free on PyPI (and TestPyPI);
   if taken, fall back to `alphai-news` (decision noted, import name still
   `alphai`). Verify `import alphai` works after `pip install -e .`.
2. **Build:** `uv build` (or `python -m build`) → sdist + wheel; check with
   `twine check dist/*`.
3. **TestPyPI dry run:** upload to TestPyPI, `pip install` from there into a
   clean venv, run `examples/quickstart.py` against prod with a real key.
4. **Publish 0.1.0:** GitHub Release tag `v0.1.0` → CI job publishes to PyPI via
   **trusted publishing (OIDC)** — no long-lived token. Manual `twine upload`
   fallback documented.
5. **Surface it (separate, optional follow-up in the main repo):** add
   `pip install alphai-sdk` to `/developers`, and a `changelog` entry **only if**
   it's a consumer-actionable announcement (run the `changelog` skill; an SDK
   release likely qualifies). This is *not* part of the SDK repo work.

---

## Execution steps (stepwise — pause for approval after each, per workflow pref)

1. **Scaffold the repo.** Create `/Users/mikhailmakeev/projects/alphai-sdk/`,
   copy this plan in as `PLAN.md`, write `pyproject.toml`, `LICENSE` (MIT),
   `README.md` skeleton, `CHANGELOG.md`, `.gitignore`, `.python-version`,
   `ruff`/`mypy` config, `src/alphai/` tree with empty modules + `py.typed`,
   `git init`. *(Standalone — does not touch the `alphai_io` checkout.)*
2. **Models + enums** (`models/`). Hand-write the Pydantic v2 models from Part A
   with `extra="allow"`, `Decimal` money, tolerant enums.
3. **Core + errors + config** (`_config.py`, `_core.py`, `errors.py`): header/
   query build, response→model/error parsing, `RateLimit`, retry/backoff.
4. **Request builders + sync `Client`** (`_requests.py`, `client.py`): the
   `news`/`symbols` resources, `_request` retry loop, `last_rate_limit`.
5. **Async `AsyncClient`** (`async_client.py`): mirror, reusing `_requests`/
   `_core`; `aiter` generators.
6. **Pagination helpers** (`pagination.py`): `NewsPage`, sync/async cursor
   iterators with `max_items`/`max_pages`.
7. **Capture fixtures + tests.** Pull a few real responses with a key, sanitize
   into `tests/fixtures/`, write the test suite (Part C). Run `ruff`, `mypy
   --strict`, `pytest` green.
8. **README + examples + CI**. Finalize docs, runnable examples, GH Actions.
9. **Build & TestPyPI dry run** (Part D 1–3). Stop before the real publish for
   explicit go-ahead.

---

## Verification

- **Offline:** `ruff check`, `ruff format --check`, `mypy --strict src/alphai`,
  `pytest` all green in CI across Python 3.10–3.13.
- **Type DX:** in an editor, `c.news.get(uid).enrichment.relevance_score`
  autocompletes as `int`; `summary.buy_value_usd` typed `Decimal | None`.
- **Live end-to-end** (with a real key against `api.alphai.io`):
  - `Client().news.list(symbol="NVDA")` returns a `NewsPage`; `.next_cursor`
    fetches the next page; `news.iter(max_items=25)` yields 25 articles.
  - `news.trending()` returns ≤10; `news.get(uid)` round-trips a uid from the
    feed; `news.related(uid)` returns ≤6.
  - `symbols.get("AAPL")`, `symbols.sentiment_summary("AAPL")`,
    `symbols.insider_summary("AAPL")` parse; money fields are `Decimal`.
  - `AsyncClient` mirror works under `asyncio.run`.
  - Bad key → `AuthenticationError`; hammering Free tier → `RateLimitError` with
    `.retry_after`; `c.last_rate_limit.remaining` decrements across calls.
- **Drift guard:** optional integration test passes against live prod; if the
  API adds a field, `extra="allow"` keeps parsing (no crash).

---

## Open follow-ups (not blocking v1)
- A tiny CLI (`alphai news --symbol NVDA`) — deferred to a later minor.
- Auto-generating models from `/api/schema/` instead of hand-writing — current
  spec is small and stable; hand-written wins on docstrings + `Decimal`. Revisit
  if the surface grows.
- Listing on `/developers` + changelog entry in the main repo after PyPI publish.
