"""Transport-agnostic helpers shared by the sync and async clients.

Nothing here performs I/O — it builds headers/params, reads rate-limit headers,
maps non-2xx responses to typed exceptions, and computes retry backoff. The two
clients differ only in how they sleep and await.
"""

from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from ._config import ClientConfig
from .errors import (
    APIStatusError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    InvalidResponseError,
    NotFoundError,
    PermissionDeniedError,
    RateLimitError,
    ServerError,
)

#: The SDK's logger. Every wait before a retry is logged here at WARNING, so even
#: with no logging configured at all Python's last-resort handler prints it to
#: stderr: a client sleeping on a 429 must not look hung. Route or silence it
#: like any other logger, e.g. ``logging.getLogger("alphai").setLevel(logging.ERROR)``.
logger = logging.getLogger("alphai")


@dataclass(frozen=True)
class RateLimit:
    """The ``X-RateLimit-*`` budget reported on a keyed response."""

    limit: int | None
    remaining: int | None
    reset: int | None

    @classmethod
    def from_headers(cls, headers: httpx.Headers) -> RateLimit | None:
        """Build from response headers, or ``None`` if the trio is absent."""
        limit = _int(headers.get("x-ratelimit-limit"))
        remaining = _int(headers.get("x-ratelimit-remaining"))
        reset = _int(headers.get("x-ratelimit-reset"))
        if limit is None and remaining is None and reset is None:
            return None
        return cls(limit=limit, remaining=remaining, reset=reset)


def build_headers(config: ClientConfig) -> dict[str, str]:
    """Default request headers (auth, accept, user-agent)."""
    return {
        "Authorization": f"Bearer {config.api_key}",
        "Accept": "application/json",
        "User-Agent": config.user_agent,
    }


def clean_params(params: dict[str, Any]) -> dict[str, Any]:
    """Drop ``None`` values and normalize enums/lists/bools for the query string."""
    out: dict[str, Any] = {}
    for key, value in params.items():
        if value is None:
            continue
        out[key] = _param_value(value)
    return out


def _param_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return [_param_value(item) for item in value]
    return value


def parse_json(response: httpx.Response) -> Any:
    """Return the parsed JSON body, or ``None`` if the body is not JSON."""
    try:
        return response.json()
    except ValueError:
        return None


def should_retry(status: int) -> bool:
    """Retry on rate limiting and server errors (all calls are idempotent GETs)."""
    return status == 429 or status >= 500


def parse_retry_after(headers: httpx.Headers) -> int | None:
    """Seconds from the ``Retry-After`` header (the API sends an integer)."""
    return _int(headers.get("retry-after"))


def read_json_body(response: httpx.Response, method: str, path: str) -> Any:
    """The parsed JSON body of a successful response.

    ``None`` for a 204 (the documented "nothing here yet", e.g.
    ``/earnings/latest/``); a 2xx without a JSON body is an
    :class:`InvalidResponseError`.
    """
    if response.status_code == 204:
        return None
    data = parse_json(response)
    if data is None:
        raise InvalidResponseError(
            f"Expected a JSON body from {method} {path} (status {response.status_code}), got none"
        )
    return data


def log_retry_wait(
    method: str,
    path: str,
    wait: float,
    retry: int,
    retries: int,
    *,
    response: httpx.Response | None = None,
    error: BaseException | None = None,
) -> None:
    """Log, at WARNING, the wait the client is about to sleep before a retry.

    ``retry`` is 1-based and ``retries`` is the configured maximum. On a 429
    the line also carries ``Retry-After`` and the daily budget from the
    ``X-RateLimit-*`` headers; those report the per-day layer only, so a 429
    with budget left is the per-minute burst cap, which no header exposes.
    """
    notes: list[str] = []
    if response is not None:
        status = response.status_code
        cause = f"HTTP {status} ({'rate limited' if status == 429 else 'server error'})"
        retry_after = response.headers.get("retry-after")
        if retry_after is not None:
            notes.append(f"Retry-After: {retry_after}s")
        rate = RateLimit.from_headers(response.headers)
        if status == 429 and rate is not None and rate.remaining is not None:
            if rate.limit is not None:
                notes.append(f"daily budget {rate.remaining}/{rate.limit} left")
            else:
                notes.append(f"daily budget {rate.remaining} left")
    else:
        cause = f"connection error ({type(error).__name__})" if error else "connection error"
    suffix = f" ({'; '.join(notes)})" if notes else ""
    logger.warning(
        "alphai: %s on %s %s; waiting %.1fs before retry %d of %d%s",
        cause,
        method,
        path,
        wait,
        retry,
        retries,
        suffix,
    )


def build_url(base_url: str, path: str) -> str:
    """Join the configured base URL with an endpoint path."""
    return f"{base_url.rstrip('/')}{path}"


def compute_backoff(
    attempt: int,
    backoff_factor: float,
    retry_after: int | None = None,
    max_retry_after: float | None = None,
) -> float:
    """Seconds to sleep before the next attempt.

    Honors ``Retry-After`` when the server provided it (capped at
    ``max_retry_after`` so a hostile/misconfigured value can't freeze the caller);
    otherwise uses exponential backoff with full jitter
    (``random(0, factor * 2**attempt)``). ``attempt`` is 0 for the first retry.
    """
    if retry_after is not None and retry_after >= 0:
        wait = float(retry_after)
        if max_retry_after is not None:
            wait = min(wait, max_retry_after)
        return wait
    ceiling = backoff_factor * (2**attempt)
    return random.uniform(0.0, ceiling)


def error_from_response(response: httpx.Response) -> APIStatusError:
    """Map a non-2xx response to the appropriate typed exception."""
    status = response.status_code
    body = parse_json(response)
    if isinstance(body, dict):
        message = body.get("message") or body.get("detail") or body.get("error")
        extra_obj = body.get("extra")
        extra = extra_obj if isinstance(extra_obj, dict) else {}
    else:
        message = (response.text or "").strip() or None
        extra = {}
    message = message or f"HTTP {status}"

    if status == 400:
        return BadRequestError(message, status=status, body=body, extra=extra)
    if status == 401:
        return AuthenticationError(message, status=status, body=body, extra=extra)
    if status == 403:
        return PermissionDeniedError(message, status=status, body=body, extra=extra)
    if status == 404:
        return NotFoundError(message, status=status, body=body, extra=extra)
    if status == 409:
        return ConflictError(message, status=status, body=body, extra=extra)
    if status == 429:
        rate = RateLimit.from_headers(response.headers)
        return RateLimitError(
            message,
            status=status,
            body=body,
            extra=extra,
            retry_after=parse_retry_after(response.headers),
            limit=rate.limit if rate else None,
            remaining=rate.remaining if rate else None,
            reset=rate.reset if rate else None,
        )
    if status >= 500:
        return ServerError(message, status=status, body=body, extra=extra)
    return APIStatusError(message, status=status, body=body, extra=extra)


def _int(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


__all__ = [
    "RateLimit",
    "build_headers",
    "build_url",
    "clean_params",
    "compute_backoff",
    "error_from_response",
    "log_retry_wait",
    "logger",
    "parse_json",
    "parse_retry_after",
    "read_json_body",
    "should_retry",
]
