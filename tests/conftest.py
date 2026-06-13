"""Shared test fixtures and helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from alphai import Client

BASE_URL = "https://api.alphai.io"
FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> Any:
    """Load a JSON fixture by name (without extension)."""
    return json.loads((FIXTURES / f"{name}.json").read_text())


def page(results: list[Any], next_cursor: str | None = None) -> dict[str, Any]:
    """Build a NewsPagination envelope around the given results."""
    return {"results": results, "next_cursor": next_cursor}


@pytest.fixture
def article() -> Any:
    return load("article")


@pytest.fixture
def insider_article() -> Any:
    return load("insider_article")


@pytest.fixture
def client() -> Iterator[Client]:
    c = Client(api_key="ak_live_test", base_url=BASE_URL, backoff_factor=0.0)
    yield c
    c.close()
