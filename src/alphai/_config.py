"""Client configuration, defaults, and API-key resolution."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ._version import __version__
from .errors import MissingAPIKeyError

DEFAULT_BASE_URL = "https://api.alphai.io"
API_KEY_ENV_VAR = "ALPHAI_API_KEY"
DEFAULT_TIMEOUT = 30.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_BACKOFF_FACTOR = 0.5
USER_AGENT = f"alphai-python/{__version__}"


@dataclass(frozen=True)
class ClientConfig:
    """Resolved, immutable configuration for a client instance."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    timeout: float = DEFAULT_TIMEOUT
    max_retries: int = DEFAULT_MAX_RETRIES
    backoff_factor: float = DEFAULT_BACKOFF_FACTOR
    user_agent: str = USER_AGENT


def resolve_api_key(api_key: str | None) -> str:
    """Return the explicit key, else ``$ALPHAI_API_KEY``, else raise."""
    key = api_key or os.environ.get(API_KEY_ENV_VAR)
    if not key:
        raise MissingAPIKeyError(
            "No API key provided. Pass api_key=... or set the "
            f"{API_KEY_ENV_VAR} environment variable. "
            "Create a key at https://alphai.io/account/api-keys"
        )
    return key


__all__ = [
    "API_KEY_ENV_VAR",
    "DEFAULT_BACKOFF_FACTOR",
    "DEFAULT_BASE_URL",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT",
    "USER_AGENT",
    "ClientConfig",
    "resolve_api_key",
]
