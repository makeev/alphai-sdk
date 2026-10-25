# Changelog

All notable changes to `alphai-sdk` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.10.0] - 2026-10-25

### Removed
- `Story.model`: the API no longer returns the name of the language model
  behind a story summary (`GET /api/stories/{story_id}/`, OpenAPI 1.53.0).
  Code that read it gets an `AttributeError` now; every other story field is
  unchanged.

## [0.9.0] - 2026-10-09

### Added
- `client.stories` (sync and async): `top()` (the last 48 hours ranked, up to
  50), `list()` / `iter()` (every story newest-first, cursor-paginated,
  `page_size` 1-50), `get(story_id)` (a `StoryLookup`: `found` with the
  `Story`, `merged` with `redirect_to`, `not_a_story` with the `article`),
  `get_story()` (follows merges, `None` for a single-publisher id),
  `materials()` / `iter_materials()` (the articles behind a story, oldest
  first). Models: `TopStories`, `StoriesPage`, `StoryCard`, `Story`,
  `StoryKeyFact`, `StoryTickerTake`, `StoryLookup`, `StoryArticleRef`,
  `StoryMaterial`, `StoryMaterialsPage`.

### Changed
- `RichNewsArticle.story_id` is now filled on every row of the feed, search,
  trending and the single-article endpoint (API 1.49.0), not only with
  `collapse_stories=True`, and it no longer changes when the story's root
  moves or two stories merge. `sources_count` / `sources` stay collapse-only.

## [0.8.2] - 2026-10-09

### Added
- `news.list` / `news.iter` take `source_type` (`gdelt`, `sec_form4`,
  `sec_form8k`, `sec_form6k`) and `item` (an 8-K item code such as `"5.02"`,
  implies 8-Ks), the feed filters the search method already had.
- `RichNewsArticle.filing` (`EightKFiling`): the structured 8-K block on 8-K
  rows, with every item code, the primary item, accession number, `filed_at`,
  `event_date` and the press-release `exhibit_url`.
- `news.insider_csv()` (sync and async): the insider feed as one CSV file
  (`format=csv`) with the feed's filters, returned as `InsiderCsvExport` with
  `rows`, `row_cap`, `truncated` and `next_cursor` from the response headers.
- `client.coverage()` (sync and async): the coverage passport, typed as
  `Coverage` / `CoverageSource` / `CoverageChannel` / `CoverageArchiveDays`,
  with `Coverage.by_source(name)`.
- `news.insider` / `news.insider_iter` take `is_10b5_1` (`False` keeps
  discretionary trades only).
- `RichNewsArticle.tickers` and `.category` shortcuts next to `uid`, `title`
  and `relevance_score`.
- Typed fields the API already sent: `RichNewsArticle.earnings` (the earnings
  read on `news.get`, `None` on most articles), `InsiderEvent.filed_at` /
  `.late_filing`, `OriginalArticle.ownership_form` and
  `NewsPagination.symbol_note`.

### Changed
- Every wait before a retry (429, 5xx, connection error) is logged at
  `WARNING` on the `alphai` logger with the seconds to wait, `Retry-After` and,
  on a 429, the daily budget left, so a client waiting out a rate limit no
  longer looks hung. Silence it with
  `logging.getLogger("alphai").setLevel(logging.ERROR)`.

### Documentation
- README: filings, the CSV export, the coverage passport, a `None` guard on
  `article.earnings`, and a note that the per-minute limit is not in any
  response header.

## [0.8.1] - 2026-10-01

### Added
- `Segment.numeric` / `.unit` / `.scale`: the companions the API attaches to
  every earnings segment from spec 1.46.0, next to the unchanged printed
  `revenue`. `scale` is `None` when nothing in the filing named the unit.
- `EarningsReport.table_scale`: the unit the filing's table headers name, which
  is the unit of any table figure the notes and `analysis` quote without one.

## [0.8.0] - 2026-09-23

### Added
- `news.search(query=...)` on `Client` and `AsyncClient`: text search with quoted
  phrases, exclusions, ticker/category/source/8-K-item filters and date windows.
- `NewsSearchPage`, `NewsSearchQueryInfo` and `SearchMatch` models expose search
  interpretation, bounded match counts, result context and cursor pagination.
- Runnable search example and guidance for partial matches, empty results and
  continuing a search with the same query and filters.

## [0.7.0] - 2026-09-21

### Added
- `news.brief`: grouped news, SEC filings and confirmed earnings dates for up to
  100 explicit tickers, with unknown-symbol and truncation information.
- `radar.snapshot` and `radar.iter`: typed market or saved-watchlist activity
  snapshots, all filters, evidence, freshness and cursor pagination. Iteration
  preserves the snapshot and stops with an error if its context changes.
- `ConflictError` for HTTP 409. Start a new Radar scan without a cursor when the
  pinned snapshot expires; scans never silently restart and mix snapshots.

### Documentation
- Runnable watchlist overview and Radar examples, including the distinction
  between a ranked Brief and complete delta ingestion.

## [0.6.3] - 2026-09-13

### Changed
- Brand spelling in the package metadata and docs is now `AlphAI` (the form on
  the logo). No API change: class names, the `alphai` module and every field
  stay exactly as they were.

## [0.6.2] - 2026-09-12

### Added
- `KeyMetric.numeric` / `.unit` / `.scale` — the machine-readable companions
  the API attaches to every earnings metric from spec 1.34.0 (the printed
  `value` is unchanged). `scale` is `None` when the filing did not name one.

## [0.6.1] - 2026-09-12

### Fixed
- `symbols.earnings_latest(ticker)` (sync and async) returns `None` when the API
  answers **204** — the documented "no read published yet" response — instead of
  raising `InvalidResponseError`. Any 204 now yields `None` from `Client.request`.

### Added
- `symbols.list(search=…)` — the name / brand / ticker-prefix lookup the API
  points you to on a 404 `unknown_symbol` (`search="bitcoin"` → `BTC-USD`,
  `search="spacex"` → `SPCX`).
- Typed `Symbol` fields that the API already sent: `status` (`active` /
  `delisted`), `delisted_at`, `renamed_to`, `brand_aliases`,
  `crypto_counterpart`, `crypto_counterpart_name`.

### Docs
- README: guard `read.analysis` and an empty `key_metrics` before indexing;
  `.allowed_params` on `BadRequestError`; honest endpoint count (11 of 17).

## [0.6.0] - 2026-08-29

### Added
- `symbols.earnings(ticker)` and `symbols.earnings_latest(ticker)` (sync and
  async), mirroring `GET /api/symbols/{ticker}/earnings/` and
  `…/earnings/latest/`. Returns typed models — `TickerEarningsHistory`
  (a ticker's published reads, newest first, capped at 20, plus
  `next_report_date`) and `LatestEarningsPointer` — with `EarningsReport`
  modelling AlphaAI's structured, filing-verified read (`key_metrics`,
  `segments`, `guidance`, `vs_prior_guidance`, `quotes`, …). An empty
  `reports` list is a normal answer, not an error.
- `Symbol.next_report_date` — the company-confirmed date of the next earnings
  report (`date | None`; `None` means no confirmed date, never an estimate).

## [0.5.0] - 2026-08-15

### Added
- `from_date=` / `to_date=` on `news.list`, `news.iter`, `news.insider` and
  `news.insider_iter` (sync and async) — the publication window the REST API
  gained today, same names as the MCP tools. Bounds are inclusive; pass a
  `datetime.date` (or a bare `YYYY-MM-DD` string) to mean the whole day — the
  server reads a bare `to_date` as that day's end, so `from_date=to_date=<day>`
  returns the day. A `datetime` is the exact instant (naive is read as UTC).
  The SDK serializes and passes through; the server enforces the rest (window
  past your plan's archive horizon = 403 on the first page, window combined
  with `sort="ingested"` = 400).

## [0.4.2] - 2026-08-04

### Fixed
- `NewsPagination.has_more` was `True` on every page in `sort="ingested"` mode,
  including a caught-up poll that returned nothing. It was derived from
  `next_cursor`, which in that mode is a polling position and is *never* null —
  so it carried no termination signal. `has_more` is now mode-aware: end-of-feed
  in `published` mode, "this poll returned rows" in `ingested` mode. A
  `while page.has_more:` loop no longer spins forever.
- `news.iter(sort="ingested")` could keep fetching after it was caught up. The
  paginator stopped on `next_cursor == cursor`, but a caught-up ingested poll
  parks the position at the **global** feed head, which advances whenever any
  row is ingested — not just one matching the caller's filter. A filtered drain
  (`symbol=…`) therefore kept requesting empty pages whenever a row landed
  between two calls, burning rate-limit budget on a race. It now stops on the
  page's own `caught_up`.

### Added
- `NewsPagination.caught_up` — the explicit, mode-aware "nothing more right
  now" signal, and the one to branch on in a polling loop.
- `sort` on `news.insider()` / `news.insider_iter()` (both clients). The insider
  feed has supported delta polling all along; the SDK simply could not ask for
  it.

### Changed
- `page_size` documentation was stale in both clients and the README: it said
  "10 or 50 (Pro only); other values are a 400". The API accepts any size in
  1-20 on any key and 21-50 on Pro. The wrong text hid the setting that keeps a
  poller current.
- README: a delta-polling section on falling behind — why a slow poller sees
  hours-old timestamps, and which dials fix it.

## [0.4.1] - 2026-07-28

### Added
- `BadRequestError.allowed_params` — the endpoint's full query-parameter
  vocabulary, which the API now returns on a 400 caused by an unknown
  parameter. Empty for 400s from anywhere else, so it never guesses.

### Fixed
- `BadRequestError.fields` was empty for the most common validation error. The
  API sends `extra.fields` as a **list** of validator entries when a query
  parameter is unknown or ill-typed, and as a **dict** when a field is rejected
  inside a view (a malformed `cursor`); only the dict was understood. Both
  shapes now normalise to `{param: [messages]}`.
- `BadRequestError` docstring no longer says a cursor can be "expired" — the
  tokens carry no expiry. An unreadable cursor was constructed or truncated
  rather than taken from a previous response's `next_cursor`.

## [0.4.0] - 2026-07-25

### Added
- `sort` on `news.list` / `news.iter` (sync and async). `sort="ingested"` is
  delta polling: the feed ordered by arrival rather than publish time, so a
  poller cannot miss an article that reached the feed late (most do - general
  news lands a median of ~33 minutes after publication). In that mode
  `next_cursor` is always set and an empty `results` means "caught up": store
  the cursor and call again later. `article.original.created_at` carries the
  moment AlphaAI received the article.

### Notes
- Cursors are mode-specific. Pass the same `sort` on every call of a run -
  replaying a cursor into the other mode returns a `400` (`BadRequestError`),
  and a corrupted cursor does too, rather than silently restarting at the head
  of the feed.
- On Free and Basic the news-archive horizon applies to where a poll resumes,
  so a cursor left unused for longer than your window returns `403`
  (`extra.reason = "archive_horizon"`). Pro has no window.

## [0.3.0] - 2026-07-11

### Added
- Structured `insider` block on insider-feed items (`news.insider` /
  `news.insider_iter`): `InsiderEvent` with `side` (`buy`/`sell`/`other`),
  raw `transaction_code`, group-summed `shares` and `total_value_usd`,
  value-weighted `avg_price_usd`, `is_10b5_1`, the reporting owner
  (`insider_name`/`insider_title`/`is_officer`/`is_director`/
  `is_ten_percent_owner`) and `transaction_date`. `None` outside the insider
  feed and on rows without paired transaction data - no more deriving the
  trade side from the headline.
- `min_relevance` (1-10) on `news.insider` / `news.insider_iter` (sync and
  async), same semantics as the main feed's parameter. Insider rows score
  deterministically from the event's summed dollar value, so this acts as an
  "only large trades" filter.

## [0.2.0] - 2026-07-09

### Added
- `page_size` on `news.list`, `news.iter`, `news.insider`, and
  `news.insider_iter` (sync and async). The API accepts 10 (the default) or
  50; 50 requires a Pro key. Previously the SDK had no way to request the
  larger page, so Pro callers paid 5x the requests for deep pagination.

## [0.1.1] - 2026-06-17

### Added
- `Symbol` now carries the multi-market fields `country`, `currency`,
  `supports_insider`, and `tv_symbol`, mirroring the API's crypto + foreign
  equity support. `country` (ISO alpha-2) and `currency` are populated for
  foreign/crypto listings (empty for US); `supports_insider` is `True` only for
  US SEC names with Form 4 data. Crypto tickers use a `-USD` quote suffix
  (e.g. `BTC-USD`); foreign listings use the Yahoo-suffix form (e.g. `VOD.L`).

### Fixed
- `RateLimitError` docstring corrected to the two-layer model (per-minute burst
  + per-day volume) — the previous "hourly quota" wording was stale.

## [0.1.0] - 2026-06-14

### Added
- Initial SDK: typed sync `Client` and async `AsyncClient` over the AlphaAI
  public REST API (`api.alphai.io`, OpenAPI 1.5.0).
- `news` resource: `list`, `iter`, `trending`, `insider`, `insider_iter`,
  `get`, `related`.
- `symbols` resource: `list`, `get`, `sentiment_summary`, `insider_summary`.
- Pydantic v2 response models, cursor auto-pagination, typed error hierarchy
  (including `InvalidResponseError`), rate-limit header inspection, and automatic
  retry on 429/5xx/connection errors with a bounded `Retry-After` (`max_retry_after`).
- Client-side validation of `uid` / `ticker` path segments; a custom `http_client`
  still gets the SDK's auth header and base URL applied on every request.
