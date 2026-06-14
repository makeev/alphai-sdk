"""Exception hierarchy for the AlphaAI SDK.

All errors derive from :class:`AlphaAIError`. Network/timeout problems raise
:class:`APIConnectionError`; any non-2xx HTTP response raises an
:class:`APIStatusError` subclass chosen by status code.
"""

from __future__ import annotations

from typing import Any


class AlphaAIError(Exception):
    """Base class for every error raised by this SDK."""


class MissingAPIKeyError(AlphaAIError):
    """No API key was passed and ``ALPHAI_API_KEY`` is not set."""


class InvalidResponseError(AlphaAIError):
    """A 2xx response could not be parsed (non-JSON / empty / wrong shape)."""


class APIConnectionError(AlphaAIError):
    """The request never produced an HTTP response (DNS, TLS, timeout, reset)."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.__cause__ = cause


class APIStatusError(AlphaAIError):
    """The API returned a non-2xx response.

    Attributes:
        status: HTTP status code.
        message: Human-readable message parsed from the body (``message`` then
            ``detail`` then ``error``), or a generic fallback.
        extra: The ``extra`` object from the error envelope (``{}`` if absent).
        body: The parsed JSON body (dict) or raw text when not JSON.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int,
        body: Any = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(f"[{status}] {message}")
        self.status = status
        self.message = message
        self.body = body
        self.extra: dict[str, Any] = extra or {}


class BadRequestError(APIStatusError):
    """400 — invalid params, malformed ticker, bad/expired cursor."""

    @property
    def fields(self) -> dict[str, Any]:
        """Per-field validation messages, when the 400 was a validation error."""
        fields = self.extra.get("fields")
        return fields if isinstance(fields, dict) else {}


class AuthenticationError(APIStatusError):
    """401 — missing, invalid, or revoked API key."""


class PermissionDeniedError(APIStatusError):
    """403 — the key is valid but not allowed to perform this action."""


class NotFoundError(APIStatusError):
    """404 — no item with that identifier."""


class RateLimitError(APIStatusError):
    """429 — the account's hourly quota was exceeded.

    Attributes:
        retry_after: Seconds to wait before retrying (from ``Retry-After``).
        limit / remaining / reset: the ``X-RateLimit-*`` trio, when present.
    """

    def __init__(
        self,
        message: str,
        *,
        status: int = 429,
        body: Any = None,
        extra: dict[str, Any] | None = None,
        retry_after: int | None = None,
        limit: int | None = None,
        remaining: int | None = None,
        reset: int | None = None,
    ) -> None:
        super().__init__(message, status=status, body=body, extra=extra)
        self.retry_after = retry_after
        self.limit = limit
        self.remaining = remaining
        self.reset = reset


class ServerError(APIStatusError):
    """5xx — the API failed to process the request."""


__all__ = [
    "APIConnectionError",
    "APIStatusError",
    "AlphaAIError",
    "AuthenticationError",
    "BadRequestError",
    "InvalidResponseError",
    "MissingAPIKeyError",
    "NotFoundError",
    "PermissionDeniedError",
    "RateLimitError",
    "ServerError",
]
