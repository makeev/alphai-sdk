# Changelog

All notable changes to `alphai-sdk` are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial SDK: typed sync `Client` and async `AsyncClient` over the AlphaAI
  public REST API (`api.alphai.io`, OpenAPI 1.5.0).
- `news` resource: `list`, `iter`, `trending`, `insider`, `insider_iter`,
  `get`, `related`.
- `symbols` resource: `list`, `get`, `sentiment_summary`, `insider_summary`.
- Pydantic v2 response models, cursor auto-pagination, typed error hierarchy,
  rate-limit header inspection, and automatic retry on 429/5xx.

## [0.1.0] - TBD
- First public release.
