# Changelog

All notable changes to `alphai-sdk` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
