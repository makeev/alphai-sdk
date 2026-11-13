"""The Form 4 sale label (API 1.61.0): ``decision`` / ``decision_reason`` on the
``insider`` block, the insider feed's ``decision`` filter (JSON and CSV) and
the 400 an invalid value answers with.

The fixtures are recorded API responses, trimmed to a few rows.
"""

from __future__ import annotations

import csv
import inspect
import io
import re
from typing import Any

import httpx
import pytest
import respx

from alphai import (
    AsyncClient,
    AsyncNewsResource,
    BadRequestError,
    Client,
    InsiderDecision,
    InsiderDecisionReason,
    InsiderEvent,
    NewsResource,
    RichNewsArticle,
)
from alphai import _requests as rq

from .conftest import BASE_URL, FIXTURES, load, page

INSIDER_URL = f"{BASE_URL}/api/news/insider/"

#: An export recorded with the label: ``decision`` and ``decision_reason`` are
#: the last two columns.
CSV_WITH_LABEL = (FIXTURES / "insider_export_decision.csv").read_text()
#: An export recorded before the label existed. An API that does not serve the
#: label sends this shape, so it has to keep reading.
CSV_WITHOUT_LABEL = (FIXTURES / "insider_export.csv").read_text()


def _csv_response(body: str) -> httpx.Response:
    return httpx.Response(
        200,
        content=body.encode(),
        headers={"Content-Type": "text/csv; charset=utf-8", "X-Alphai-Truncated": "false"},
    )


# --- the decision filter ---------------------------------------------------


def _insider_params(client: Client, **kwargs: Any) -> httpx.QueryParams:
    route = respx.get(INSIDER_URL).mock(return_value=httpx.Response(200, json=page([], None)))
    client.news.insider(**kwargs)
    return route.calls.last.request.url.params


@respx.mock
def test_decision_string(client: Client) -> None:
    params = _insider_params(client, decision="discretionary")
    assert params.get_list("decision") == ["discretionary"]


@pytest.mark.parametrize("member", list(InsiderDecision))
@respx.mock
def test_decision_enum_is_sent_as_its_value(client: Client, member: InsiderDecision) -> None:
    params = _insider_params(client, decision=member)
    assert params.get_list("decision") == [member.value]


def test_builder_normalizes_the_enum_to_a_plain_string() -> None:
    value = rq.build_news_insider_params(decision=InsiderDecision.PLAN_LIKE)["decision"]
    assert value == "plan_like"
    assert type(value) is str
    assert rq.build_news_insider_params()["decision"] is None


@respx.mock
def test_decision_omitted_by_default(client: Client) -> None:
    assert "decision" not in _insider_params(client, symbol="NVDA")
    assert "decision" not in _insider_params(client, decision=None)


@respx.mock
def test_decision_composes_with_the_other_filters(client: Client) -> None:
    params = _insider_params(
        client,
        decision=InsiderDecision.DISCRETIONARY,
        is_10b5_1=False,
        sort="ingested",
        symbol="MET",
        min_relevance=6,
        cursor="abc",
        page_size=20,
    )
    assert params["decision"] == "discretionary"
    assert params["is_10b5_1"] == "false"
    assert params["sort"] == "ingested"
    assert params["symbol"] == "MET"
    assert params["min_relevance"] == "6"
    assert params["cursor"] == "abc"
    assert params["page_size"] == "20"

    params = _insider_params(
        client, decision="plan_like", from_date="2026-11-01", to_date="2026-11-13"
    )
    assert params["decision"] == "plan_like"
    assert (params["from_date"], params["to_date"]) == ("2026-11-01", "2026-11-13")


@respx.mock
def test_a_value_this_sdk_does_not_know_is_sent_as_is(client: Client) -> None:
    # Like the other enum-or-string filters: the server decides what is valid.
    assert _insider_params(client, decision="reviewed")["decision"] == "reviewed"


@respx.mock
def test_insider_iter_threads_decision_onto_every_page(client: Client) -> None:
    rows = load("insider_decision_unknown")["results"]
    route = respx.get(INSIDER_URL).mock(
        side_effect=[
            httpx.Response(200, json=page(rows[:1], "c2")),
            httpx.Response(200, json=page(rows[1:], None)),
        ]
    )
    items = list(client.news.insider_iter(decision=InsiderDecision.UNKNOWN, is_10b5_1=False))
    assert [a.uid for a in items] == [r["original"]["uid"] for r in rows]
    for call in route.calls:
        assert call.request.url.params.get_list("decision") == ["unknown"]
        assert call.request.url.params["is_10b5_1"] == "false"
    assert route.calls[1].request.url.params["cursor"] == "c2"


@respx.mock
def test_insider_csv_sends_decision(client: Client) -> None:
    route = respx.get(INSIDER_URL).mock(return_value=_csv_response(CSV_WITH_LABEL))
    client.news.insider_csv(decision=InsiderDecision.DISCRETIONARY, symbol="MET", sort="ingested")
    params = route.calls[0].request.url.params
    assert params["format"] == "csv"
    assert params["decision"] == "discretionary"
    assert params["symbol"] == "MET"
    assert params["sort"] == "ingested"

    client.news.insider_csv()
    assert "decision" not in route.calls[1].request.url.params


@pytest.mark.parametrize("resource", [NewsResource, AsyncNewsResource])
def test_decision_is_a_filter_of_the_insider_feed_only(resource: type) -> None:
    for name in ("insider", "insider_iter", "insider_csv"):
        assert "decision" in inspect.signature(getattr(resource, name)).parameters
    # /api/news/ answers `decision` with a 400, so the general feed and the
    # search do not offer it.
    for name in ("list", "iter", "search"):
        assert "decision" not in inspect.signature(getattr(resource, name)).parameters


@respx.mock
async def test_async_insider_iter_and_csv_send_decision() -> None:
    feed = load("insider_decision_plan_like")
    route = respx.get(INSIDER_URL).mock(
        side_effect=[
            httpx.Response(200, json=feed),
            httpx.Response(200, json=page(feed["results"], None)),
            _csv_response(CSV_WITH_LABEL),
        ]
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        result = await client.news.insider(decision=InsiderDecision.PLAN_LIKE)
        items = [a async for a in client.news.insider_iter(decision="plan_like")]
        export = await client.news.insider_csv(decision="plan_like", is_10b5_1=False)
    assert [c.request.url.params["decision"] for c in route.calls] == ["plan_like"] * 3
    assert route.calls[2].request.url.params["format"] == "csv"
    assert route.calls[2].request.url.params["is_10b5_1"] == "false"
    block = result.results[0].insider
    assert block is not None
    assert block.decision is InsiderDecision.PLAN_LIKE
    assert block.decision_reason is InsiderDecisionReason.PLAN_10B5_1
    assert len(items) == 2
    assert export.text == CSV_WITH_LABEL


# --- the label on the insider block ----------------------------------------


def _blocks(name: str) -> list[InsiderEvent]:
    blocks = []
    for raw in load(name)["results"]:
        block = RichNewsArticle.model_validate(raw).insider
        assert isinstance(block, InsiderEvent)
        blocks.append(block)
    return blocks


@pytest.mark.parametrize(
    ("value", "reasons"),
    [
        (
            InsiderDecision.DISCRETIONARY,
            [InsiderDecisionReason.OPEN_MARKET, InsiderDecisionReason.OPEN_MARKET],
        ),
        (
            InsiderDecision.PLAN_LIKE,
            [InsiderDecisionReason.PLAN_10B5_1, InsiderDecisionReason.PLAN_10B5_1],
        ),
        (
            InsiderDecision.UNKNOWN,
            [InsiderDecisionReason.COVER_AMBIGUOUS, InsiderDecisionReason.PARTIAL_VEST_SALE],
        ),
    ],
)
@respx.mock
def test_filtered_page_carries_only_its_label(
    client: Client, value: InsiderDecision, reasons: list[InsiderDecisionReason]
) -> None:
    route = respx.get(INSIDER_URL).mock(
        return_value=httpx.Response(200, json=load(f"insider_decision_{value.value}"))
    )
    result = client.news.insider(decision=value)
    assert route.calls[0].request.url.params["decision"] == value.value
    assert result.next_cursor
    blocks = [a.insider for a in result.results]
    assert all(isinstance(b, InsiderEvent) for b in blocks)
    # Members, not bare strings: `is` works, and so does a string comparison.
    assert len(blocks) == 2
    assert all(b.decision is value for b in blocks if b)
    assert all(b.decision == value.value for b in blocks if b)
    assert [b.decision_reason for b in blocks if b] == reasons
    assert all(isinstance(b.decision_reason, InsiderDecisionReason) for b in blocks if b)
    # Only sales are labelled.
    assert {(b.side, b.transaction_code) for b in blocks if b} == {("sell", "S")}


@respx.mock
def test_unfiltered_page_has_unlabelled_purchases_next_to_labelled_sales(client: Client) -> None:
    respx.get(INSIDER_URL).mock(
        return_value=httpx.Response(200, json=load("insider_decision_unfiltered"))
    )
    blocks = [a.insider for a in client.news.insider().results]
    assert [(b.transaction_code, b.decision, b.decision_reason) for b in blocks if b] == [
        ("P", None, None),
        ("S", InsiderDecision.DISCRETIONARY, InsiderDecisionReason.OPEN_MARKET),
        ("P", None, None),
    ]
    # The rest of the block is read as before.
    sale = blocks[1]
    assert sale is not None
    assert sale.is_10b5_1 is False
    assert sale.insider_name == "Elsztain Alejandro Gustavo"
    assert str(sale.total_value_usd) == "124103.46"


def test_labels_split_the_feed() -> None:
    # The three filtered feeds plus the events without a sale add up to the
    # unfiltered one: every row of the unfiltered page sits in exactly one of
    # the four, by its label.
    pages = {value: _blocks(f"insider_decision_{value.value}") for value in InsiderDecision}
    for value, blocks in pages.items():
        assert {b.decision for b in blocks} == {value}
    by_label: dict[Any, list[str]] = {}
    for raw in load("insider_decision_unfiltered")["results"]:
        art = RichNewsArticle.model_validate(raw)
        assert art.insider is not None
        by_label.setdefault(art.insider.decision, []).append(art.uid)
    assert set(by_label) == {None, InsiderDecision.DISCRETIONARY}
    assert len(by_label[None]) == 2
    # The labelled sale is the head of the `decision=discretionary` page and is
    # on neither of the other two.
    filtered_uids = {
        value: [r["original"]["uid"] for r in load(f"insider_decision_{value.value}")["results"]]
        for value in InsiderDecision
    }
    (sale_uid,) = by_label[InsiderDecision.DISCRETIONARY]
    assert filtered_uids[InsiderDecision.DISCRETIONARY][0] == sale_uid
    assert sale_uid not in filtered_uids[InsiderDecision.PLAN_LIKE]
    assert sale_uid not in filtered_uids[InsiderDecision.UNKNOWN]
    for uid in by_label[None]:
        assert all(uid not in uids for uids in filtered_uids.values())


@respx.mock
def test_single_article_carries_the_label(client: Client) -> None:
    # /api/news/{uid}/ returns the same row shape as the feed.
    raw = load("insider_decision_unknown")["results"][1]
    uid = raw["original"]["uid"]
    respx.get(f"{BASE_URL}/api/news/{uid}/").mock(return_value=httpx.Response(200, json=raw))
    block = client.news.get(uid).insider
    assert block is not None
    assert block.decision is InsiderDecision.UNKNOWN
    assert block.decision_reason is InsiderDecisionReason.PARTIAL_VEST_SALE


def _block(**overrides: Any) -> dict[str, Any]:
    block = dict(load("insider_decision_unfiltered")["results"][1]["insider"])
    block.update(overrides)
    return block


def test_label_is_none_when_the_api_sends_null() -> None:
    # Purchases, and every event on an API that does not serve the label.
    event = InsiderEvent.model_validate(_block(decision=None, decision_reason=None))
    assert event.decision is None
    assert event.decision_reason is None


def test_label_is_none_when_the_api_sends_no_such_fields() -> None:
    block = _block()
    del block["decision"], block["decision_reason"]
    event = InsiderEvent.model_validate(block)
    assert (event.decision, event.decision_reason) == (None, None)
    assert InsiderEvent().decision is None
    assert InsiderEvent().decision_reason is None


def test_older_fixture_without_the_label_still_parses(insider_article: dict) -> None:
    assert RichNewsArticle.model_validate(insider_article).insider is None


def test_a_sale_to_the_issuer_is_not_labelled() -> None:
    # Code D reads as side "other" on the feed and carries no label.
    event = InsiderEvent.model_validate(
        _block(side="other", transaction_code="D", decision=None, decision_reason=None)
    )
    assert (event.side, event.transaction_code) == ("other", "D")
    assert event.decision is None
    assert event.decision_reason is None


def test_unknown_sale_can_come_without_a_reason() -> None:
    event = InsiderEvent.model_validate(_block(decision="unknown", decision_reason=None))
    assert event.decision is InsiderDecision.UNKNOWN
    assert event.decision_reason is None


def test_values_this_sdk_does_not_know_pass_through_as_str() -> None:
    event = InsiderEvent.model_validate(
        _block(decision="reviewed", decision_reason="gift_then_sale", future_field=1)
    )
    assert event.decision == "reviewed"
    assert not isinstance(event.decision, InsiderDecision)
    assert event.decision_reason == "gift_then_sale"
    assert not isinstance(event.decision_reason, InsiderDecisionReason)
    assert event.model_extra == {"future_field": 1}
    # A known decision next to a reason added later still gives the member.
    mixed = InsiderEvent.model_validate(_block(decision_reason="gift_then_sale"))
    assert mixed.decision is InsiderDecision.DISCRETIONARY
    assert mixed.decision_reason == "gift_then_sale"


def test_label_survives_a_dump_as_plain_strings() -> None:
    dumped = InsiderEvent.model_validate(_block()).model_dump(mode="json")
    assert dumped["decision"] == "discretionary"
    assert dumped["decision_reason"] == "open_market"


def test_decision_enum_matches_the_api_vocabulary() -> None:
    # The invalid-value 400 names every allowed value, in the API's own order.
    expected = load("insider_decision_invalid_400")["body"]["extra"]["fields"][0]["ctx"]["expected"]
    assert [m.value for m in InsiderDecision] == re.findall(r"'([a-z_]+)'", expected)


def test_decision_reason_enum_lists_the_twelve_reasons() -> None:
    assert [m.value for m in InsiderDecisionReason] == [
        "plan_10b5_1",
        "tax_withholding",
        "exercise_cover",
        "stated_non_discretionary",
        "open_market",
        "exercise_and_sell",
        "sold_all_vested",
        "partial_vest_sale",
        "cover_ambiguous",
        "mixed_acquisitions",
        "price_disputed",
        "no_lines",
    ]


# --- the 400s --------------------------------------------------------------


def _mock_invalid_400() -> tuple[respx.Route, dict[str, Any]]:
    recorded = load("insider_decision_invalid_400")
    route = respx.get(INSIDER_URL).mock(
        return_value=httpx.Response(recorded["status"], json=recorded["body"])
    )
    return route, recorded["body"]


@respx.mock
def test_invalid_decision_is_a_bad_request(client: Client) -> None:
    route, body = _mock_invalid_400()
    with pytest.raises(BadRequestError) as exc:
        client.news.insider(decision="bogus")
    assert route.calls[0].request.url.params["decision"] == "bogus"
    err = exc.value
    assert err.status == 400
    assert err.message == "Validation error"
    assert err.body == body
    assert err.fields == {"decision": ["Input should be 'discretionary', 'plan_like' or 'unknown'"]}
    assert {"decision", "is_10b5_1", "sort", "format"} <= set(err.allowed_params)
    assert err.extra["docs"] == "https://alphai.io/developers"


@respx.mock
def test_invalid_decision_is_not_retried(client: Client) -> None:
    route, _ = _mock_invalid_400()
    with pytest.raises(BadRequestError):
        list(client.news.insider_iter(decision="bogus"))
    assert route.call_count == 1


@respx.mock
def test_invalid_decision_on_the_csv_export_is_the_same_400(client: Client) -> None:
    # Validation errors are JSON bodies in either format, sent before any row.
    _mock_invalid_400()
    with pytest.raises(BadRequestError) as exc:
        client.news.insider_csv(decision="bogus")
    assert list(exc.value.fields) == ["decision"]


@respx.mock
async def test_async_invalid_decision_is_a_bad_request() -> None:
    _mock_invalid_400()
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        with pytest.raises(BadRequestError) as exc:
            await client.news.insider(decision="bogus")
        with pytest.raises(BadRequestError):
            await client.news.insider_csv(decision="bogus")
    assert list(exc.value.fields) == ["decision"]
    assert "decision" in exc.value.allowed_params


@respx.mock
def test_filter_refused_by_an_api_without_the_label(client: Client) -> None:
    # Not a recorded response: an API that does not serve the label refuses the
    # filter with a 400 raised inside the view, which arrives in the dict shape
    # of `extra.fields`. It surfaces as the same error class.
    respx.get(INSIDER_URL).mock(
        return_value=httpx.Response(
            400,
            json={
                "message": "Validation error",
                "extra": {
                    "fields": {
                        "decision": ["The decision filter is not available on this API yet."]
                    }
                },
            },
        )
    )
    with pytest.raises(BadRequestError) as exc:
        client.news.insider(decision=InsiderDecision.DISCRETIONARY)
    assert "not available" in exc.value.fields["decision"][0]


# --- the CSV columns -------------------------------------------------------


@respx.mock
def test_csv_label_is_the_last_two_columns(client: Client) -> None:
    respx.get(INSIDER_URL).mock(return_value=_csv_response(CSV_WITH_LABEL))
    export = client.news.insider_csv()
    records = list(csv.DictReader(io.StringIO(export.text)))
    assert len(records) == 7
    assert list(records[0])[-3:] == ["summary", "decision", "decision_reason"]
    assert [(r["transaction_code"], r["decision"], r["decision_reason"]) for r in records] == [
        ("P", "", ""),  # a purchase: empty cells
        ("S", "discretionary", "open_market"),
        ("P", "", ""),
        ("S", "plan_like", "plan_10b5_1"),
        ("D", "", ""),  # a sale to the issuer is not labelled either
        ("S", "plan_like", "tax_withholding"),
        ("S", "unknown", "cover_ambiguous"),
    ]
    # The cells are the enum values, so they convert directly.
    assert InsiderDecision(records[1]["decision"]) is InsiderDecision.DISCRETIONARY
    assert InsiderDecisionReason(records[5]["decision_reason"]) is (
        InsiderDecisionReason.TAX_WITHHOLDING
    )
    # A tax sale on vesting is not under a 10b5-1 plan, yet it is not the
    # insider's choice: `is_10b5_1=false` alone would have kept it.
    assert (records[5]["is_10b5_1"], records[5]["decision"]) == ("false", "plan_like")
    assert (records[4]["side"], records[4]["transaction_code"]) == ("other", "D")


def test_csv_cells_match_the_json_blocks() -> None:
    records = {r["uid"]: r for r in csv.DictReader(io.StringIO(CSV_WITH_LABEL))}
    checked = 0
    for name in (
        "insider_decision_unfiltered",
        "insider_decision_plan_like",
        "insider_decision_unknown",
    ):
        for raw in load(name)["results"]:
            art = RichNewsArticle.model_validate(raw)
            row = records.get(art.uid)
            if row is None:
                continue
            assert art.insider is not None
            assert row["decision"] == (art.insider.decision or "")
            assert row["decision_reason"] == (art.insider.decision_reason or "")
            assert row["transaction_code"] == art.insider.transaction_code
            checked += 1
    assert checked == 5


@respx.mock
def test_csv_without_the_label_columns_still_reads(client: Client) -> None:
    # The SDK hands the file over as text and requires no column, so a file
    # that ends at `summary` is read like any other. Read the label by name.
    respx.get(INSIDER_URL).mock(return_value=_csv_response(CSV_WITHOUT_LABEL))
    export = client.news.insider_csv(symbol="NVDA")
    assert export.text == CSV_WITHOUT_LABEL
    records = list(csv.DictReader(io.StringIO(export.text)))
    assert len(records) == 3
    assert list(records[0])[-1] == "summary"
    assert all(r.get("decision") is None and r.get("decision_reason") is None for r in records)
