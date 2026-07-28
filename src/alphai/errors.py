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
    """400 — invalid params, malformed ticker, or a malformed cursor.

    (A cursor is never rejected for age: the tokens carry no expiry. An
    unreadable one means it was constructed or truncated rather than taken
    from a previous response's ``next_cursor``.)
    """

    @property
    def fields(self) -> dict[str, Any]:
        """Per-field validation messages, when the 400 was a validation error.

        The API sends ``extra.fields`` in two shapes and both are normalised
        here to ``{param: [messages]}``:

        - a **list** of validator entries (``{"loc": ["skip"], "msg": …}``) —
          what an unknown or ill-typed *query parameter* produces, i.e. the
          common case;
        - a **dict** of ``{field: messages}`` — what a field rejected inside a
          view produces (a malformed ``cursor``, for one).

        Earlier releases only understood the dict, so the list shape silently
        came back as ``{}``.
        """
        fields = self.extra.get("fields")
        if isinstance(fields, dict):
            return fields
        if not isinstance(fields, list):
            return {}
        normalised: dict[str, Any] = {}
        for entry in fields:
            if not isinstance(entry, dict):
                continue
            loc = entry.get("loc") or ["_"]
            key = ".".join(str(part) for part in loc) if isinstance(loc, list) else str(loc)
            normalised.setdefault(key, []).append(entry.get("msg", ""))
        return normalised

    @property
    def allowed_params(self) -> list[str]:
        """Every query parameter the endpoint accepts, when the API said so.

        Sent on a 400 caused by an unknown query parameter, so a caller (or an
        agent) can correct itself without going to the docs. Empty when the 400
        came from somewhere other than query-parameter validation.
        """
        allowed = self.extra.get("allowed_params")
        return [str(p) for p in allowed] if isinstance(allowed, list) else []


class AuthenticationError(APIStatusError):
    """401 — missing, invalid, or revoked API key."""


class PermissionDeniedError(APIStatusError):
    """403 — the key is valid but not allowed to perform this action."""


class NotFoundError(APIStatusError):
    """404 — no item with that identifier."""


class RateLimitError(APIStatusError):
    """429 — a rate limit was exceeded (per-minute burst or per-day volume).

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
