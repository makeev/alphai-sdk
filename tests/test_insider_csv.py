"""``news.insider_csv`` — the insider feed as one CSV file (``format=csv``)."""

from __future__ import annotations

import csv
import io

import httpx
import pytest
import respx

from alphai import (
    AsyncClient,
    BadRequestError,
    Client,
    InsiderCsvExport,
    InvalidResponseError,
    RateLimitError,
)

from .conftest import BASE_URL, FIXTURES

CSV_BODY = (FIXTURES / "insider_export.csv").read_text()


def _csv_response(
    body: str = CSV_BODY,
    *,
    truncated: str = "false",
    rows: str = "3",
    next_cursor: str | None = None,
) -> httpx.Response:
    headers = {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": 'attachment; filename="alphai-insider-2026-10-09.csv"',
        "X-Alphai-Rows": rows,
        "X-Alphai-Row-Cap": "500",
        "X-Alphai-Truncated": truncated,
    }
    if next_cursor is not None:
        headers["X-Alphai-Next-Cursor"] = next_cursor
    return httpx.Response(200, content=body.encode(), headers=headers)


@respx.mock
def test_insider_csv_request_shape(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(return_value=_csv_response())
    client.news.insider_csv(
        symbol="NVDA",
        min_relevance=6,
        is_10b5_1=False,
        from_date="2026-09-01",
        to_date="2026-09-30",
    )
    request = route.calls[0].request
    params = request.url.params
    assert params["format"] == "csv"
    assert params["symbol"] == "NVDA"
    assert params["min_relevance"] == "6"
    assert params["is_10b5_1"] == "false"
    assert params["from_date"] == "2026-09-01"
    assert params["to_date"] == "2026-09-30"
    assert "page_size" not in params  # no effect on an export
    # format=csv with a JSON-only Accept is a 406 on the API.
    assert request.headers["Accept"].startswith("text/csv")
    assert request.headers["Authorization"] == "Bearer ak_live_test"


@respx.mock
def test_json_requests_keep_the_json_accept(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(200, json={"results": [], "next_cursor": None})
    )
    client.news.insider()
    assert route.calls[0].request.headers["Accept"] == "application/json"


@respx.mock
def test_insider_csv_complete_file(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/insider/").mock(return_value=_csv_response())
    export = client.news.insider_csv(symbol="NVDA")
    assert isinstance(export, InsiderCsvExport)
    assert export.rows == 3
    assert export.row_cap == 500
    assert export.truncated is None  # header "false": the file holds everything
    assert export.next_cursor is None
    assert export.filename == "alphai-insider-2026-10-09.csv"

    records = list(csv.DictReader(io.StringIO(export.text)))
    assert len(records) == export.rows
    first = records[0]
    assert first["uid"] == "403644bc7c09e2be"
    assert first["side"] == "sell"
    assert first["total_value_usd"] == "6786532.59"
    assert first["insider_title"] == "EVP, General Counsel and Sec"  # quoted comma survives
    assert list(first)[-1] == "summary"


@pytest.mark.parametrize("reason", ["row_cap", "archive_horizon"])
@respx.mock
def test_insider_csv_truncated_carries_reason_and_cursor(client: Client, reason: str) -> None:
    respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=_csv_response(truncated=reason, next_cursor="MjAyNi0wOS0xOA==")
    )
    export = client.news.insider_csv()
    assert export.truncated == reason
    assert export.next_cursor == "MjAyNi0wOS0xOA=="


@respx.mock
def test_insider_csv_continues_with_cursor_and_sort(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(return_value=_csv_response())
    client.news.insider_csv(sort="ingested", cursor="abc")
    params = route.calls[0].request.url.params
    assert params["cursor"] == "abc"
    assert params["sort"] == "ingested"


@respx.mock
def test_insider_csv_empty_file(client: Client) -> None:
    header_only = CSV_BODY.splitlines(keepends=True)[0]
    respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=_csv_response(header_only, rows="0")
    )
    export = client.news.insider_csv(symbol="ZZZZ")
    assert export.rows == 0
    assert list(csv.DictReader(io.StringIO(export.text))) == []


@respx.mock
def test_insider_csv_validation_error_is_json_400(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(
            400,
            json={
                "message": "Validation error",
                "extra": {"fields": {"from_date": ["cannot be combined with sort=ingested"]}},
            },
        )
    )
    with pytest.raises(BadRequestError) as info:
        client.news.insider_csv(sort="ingested", from_date="2026-09-01")
    assert "from_date" in info.value.fields


@respx.mock
def test_insider_csv_429_is_retried(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        side_effect=[
            httpx.Response(429, json={"message": "throttled"}, headers={"Retry-After": "0"}),
            _csv_response(),
        ]
    )
    assert client.news.insider_csv().rows == 3
    assert route.call_count == 2


@respx.mock
def test_insider_csv_429_exhausted() -> None:
    throttled = httpx.Response(429, json={"message": "throttled"}, headers={"Retry-After": "0"})
    respx.get(f"{BASE_URL}/api/news/insider/").mock(return_value=throttled)
    with (
        Client(api_key="ak_live_test", base_url=BASE_URL, max_retries=0) as client,
        pytest.raises(RateLimitError),
    ):
        client.news.insider_csv()


@respx.mock
def test_insider_csv_rejects_a_json_body(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(200, json={"results": [], "next_cursor": None})
    )
    with pytest.raises(InvalidResponseError):
        client.news.insider_csv()


@respx.mock
def test_insider_csv_missing_headers_are_none(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=httpx.Response(
            200, content=CSV_BODY.encode(), headers={"Content-Type": "text/csv"}
        )
    )
    export = client.news.insider_csv()
    assert (export.rows, export.row_cap, export.next_cursor, export.filename) == (
        None,
        None,
        None,
        None,
    )
    assert export.text == CSV_BODY


@respx.mock
async def test_async_insider_csv() -> None:
    route = respx.get(f"{BASE_URL}/api/news/insider/").mock(
        return_value=_csv_response(truncated="row_cap", next_cursor="next")
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        export = await client.news.insider_csv(symbol="NVDA", is_10b5_1=True)
    assert export.truncated == "row_cap"
    assert export.next_cursor == "next"
    request = route.calls[0].request
    assert request.url.params["format"] == "csv"
    assert request.url.params["is_10b5_1"] == "true"
    assert request.headers["Accept"].startswith("text/csv")
