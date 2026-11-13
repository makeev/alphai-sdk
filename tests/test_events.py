"""Corporate events (API 1.61.0): the feed's ``event_type`` filter, the typed
``event`` block on news rows, and the two 400s the filter can answer with.

The fixtures are recorded API responses, trimmed to a few rows.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx
import pytest
import respx

from alphai import (
    AsyncClient,
    BadRequestError,
    Client,
    CorporateEvent,
    CorporateEventFact,
    CorporateEventType,
    CorporateSecondaryEvent,
    EightKFiling,
    RichNewsArticle,
)

from .conftest import BASE_URL, load, page

# --- the event_type filter -------------------------------------------------


def _feed_params(client: Client, **kwargs: Any) -> httpx.QueryParams:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=page([], None))
    )
    client.news.list(**kwargs)
    return route.calls.last.request.url.params


@respx.mock
def test_event_type_single_string(client: Client) -> None:
    params = _feed_params(client, event_type="buyback")
    assert params.get_list("event_type") == ["buyback"]


@respx.mock
def test_event_type_enum(client: Client) -> None:
    params = _feed_params(client, event_type=CorporateEventType.M_AND_A)
    assert params.get_list("event_type") == ["m_and_a"]


@respx.mock
def test_event_type_list_is_repeated_like_category(client: Client) -> None:
    # Same wire form as `category`: one query parameter per value.
    params = _feed_params(
        client,
        category=["corporate_actions", "earnings"],
        event_type=[CorporateEventType.BUYBACK, "dividend"],
    )
    assert params.get_list("event_type") == ["buyback", "dividend"]
    assert params.get_list("category") == ["corporate_actions", "earnings"]


@respx.mock
def test_event_type_composes_with_other_filters(client: Client) -> None:
    params = _feed_params(
        client,
        event_type="m_and_a",
        symbol="NVDA",
        source_type="sec_form8k",
        from_date="2026-11-01",
    )
    assert params.get_list("event_type") == ["m_and_a"]
    assert params["symbol"] == "NVDA"
    assert params.get_list("source_type") == ["sec_form8k"]
    assert params["from_date"] == "2026-11-01"


@respx.mock
def test_event_type_omitted_by_default(client: Client) -> None:
    assert "event_type" not in _feed_params(client, symbol="NVDA")
    assert "event_type" not in _feed_params(client, event_type=[])


@respx.mock
def test_iter_threads_event_type_onto_every_page(client: Client) -> None:
    rows = load("event_feed")["results"]
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        side_effect=[
            httpx.Response(200, json=page(rows[:2], "c2")),
            httpx.Response(200, json=page(rows[2:], None)),
        ]
    )
    items = list(client.news.iter(event_type=["dividend", CorporateEventType.M_AND_A]))
    assert [a.uid for a in items] == [r["original"]["uid"] for r in rows]
    for call in route.calls:
        assert call.request.url.params.get_list("event_type") == ["dividend", "m_and_a"]
    assert route.calls[1].request.url.params["cursor"] == "c2"


@respx.mock
async def test_async_list_and_iter_send_event_type() -> None:
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=load("event_feed"))
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        result = await client.news.list(event_type=CorporateEventType.DIVIDEND)
        items = [a async for a in client.news.iter(event_type=["buyback", "offering"], max_pages=1)]
    assert route.calls[0].request.url.params.get_list("event_type") == ["dividend"]
    assert route.calls[1].request.url.params.get_list("event_type") == ["buyback", "offering"]
    assert result.results[0].event is not None
    assert len(items) == 3
    assert all(isinstance(a.event, CorporateEvent) for a in items)


# --- the event block -------------------------------------------------------


@respx.mock
def test_feed_rows_parse_the_event_block(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=load("event_feed"))
    )
    result = client.news.list(event_type=["dividend", "m_and_a"], source_type="sec_form8k")
    assert result.next_cursor
    earnings, dividend, deal = (a.event for a in result.results)

    # A dividend declared inside an earnings release: the main event is the
    # release, the dividend rides in `also` and is what the filter matched.
    assert isinstance(earnings, CorporateEvent)
    assert earnings.type is CorporateEventType.EARNINGS
    assert earnings.role == "issuer"
    assert earnings.stage is None
    assert earnings.counterparty is None
    assert earnings.facts == []
    assert earnings.verified is True
    assert len(earnings.also) == 1
    secondary = earnings.also[0]
    assert isinstance(secondary, CorporateSecondaryEvent)
    assert secondary.type is CorporateEventType.DIVIDEND
    assert [f.name for f in secondary.facts] == ["record_date", "payable_date"]
    assert secondary.facts[0].value == "November 5, 2026"
    assert secondary.facts[0].number is None

    # A dividend with figures: the quote stays verbatim, the number is parsed.
    assert isinstance(dividend, CorporateEvent)
    assert dividend.type is CorporateEventType.DIVIDEND
    assert dividend.type == "dividend"
    assert dividend.verified is True
    assert dividend.also == []
    facts = {f.name: f for f in dividend.facts}
    assert list(facts) == [
        "amount_per_share",
        "frequency",
        "kind",
        "prior_amount_per_share",
        "change_pct",
        "record_date",
        "payable_date",
    ]
    amount = facts["amount_per_share"]
    assert isinstance(amount, CorporateEventFact)
    assert amount.value == "$0.19 per share"
    assert amount.number == 0.19
    assert isinstance(amount.number, float)
    assert amount.number_high is None
    assert amount.unit == "USD"
    assert amount.scale is None
    assert (facts["change_pct"].value, facts["change_pct"].number) == ("11.8%", 11.8)
    assert facts["change_pct"].unit == "percent"
    # Enumerated and date facts carry no number.
    assert facts["kind"].value == "increase"
    assert facts["kind"].number is None
    assert facts["record_date"].value == "November 27, 2026"
    assert facts["record_date"].unit is None

    # A deal: stage, role and counterparty are lifted next to the facts.
    assert isinstance(deal, CorporateEvent)
    assert deal.type is CorporateEventType.M_AND_A
    assert deal.stage == "announced"
    assert deal.role == "acquirer"
    assert deal.counterparty == "80 Mile plc"
    deal_facts = {f.name: f for f in deal.facts}
    assert deal_facts["counterparty"].value == "80 Mile plc"
    assert deal_facts["consideration"].value == "stock"
    assert deal_facts["premium_pct"].value == "approximately 71%"
    assert deal_facts["premium_pct"].number == 71.0
    assert deal_facts["premium_pct"].unit == "percent"
    assert deal_facts["stage"].value == deal.stage
    loan = deal.also[0]
    assert loan.type is CorporateEventType.DEBT_FINANCING
    amount = {f.name: f for f in loan.facts}["amount"]
    assert amount.value == "£3 million"
    assert (amount.number, amount.unit, amount.scale) == (3.0, "GBP", "millions")


@respx.mock
def test_event_sits_next_to_the_filing_block(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(200, json=load("event_feed"))
    )
    art = client.news.list(event_type="m_and_a").results[2]
    assert isinstance(art.filing, EightKFiling)
    assert art.filing.items == ["7.01"]
    assert art.filing.filed_at == datetime(2026, 11, 13, 14, 24, 18, tzinfo=timezone.utc)
    assert art.event is not None and art.event.type is CorporateEventType.M_AND_A
    assert art.insider is None
    assert art.earnings is None


@respx.mock
def test_single_article_carries_the_event(client: Client) -> None:
    uid = "a3bec214ddb5205c"
    respx.get(f"{BASE_URL}/api/news/{uid}/").mock(
        return_value=httpx.Response(200, json=load("event_article"))
    )
    art = client.news.get(uid)
    event = art.event
    assert isinstance(event, CorporateEvent)
    assert event.type is CorporateEventType.DIVIDEND
    assert event.role == "issuer"
    # A fact was withheld by the check against the document: the ones that
    # are present passed it, and `verified` says the list is not complete.
    assert event.verified is False
    assert {f.name: f.value for f in event.facts} == {
        "frequency": "quarterly",
        "kind": "regular",
        "payable_date": "January 15, 2027",
        "record_date": "December 23, 2026",
    }
    assert all(f.number is None and f.number_high is None for f in event.facts)
    assert event.also == []


@respx.mock
async def test_async_single_article_carries_the_event() -> None:
    uid = "a3bec214ddb5205c"
    respx.get(f"{BASE_URL}/api/news/{uid}/").mock(
        return_value=httpx.Response(200, json=load("event_article"))
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        art = await client.news.get(uid)
    assert art.event is not None
    assert art.event.type is CorporateEventType.DIVIDEND


def test_event_is_none_on_rows_without_one(article: dict, insider_article: dict) -> None:
    # Press and Form 4 rows, and any row whose document has not been read yet.
    assert RichNewsArticle.model_validate(article).event is None
    assert RichNewsArticle.model_validate({**article, "event": None}).event is None
    assert RichNewsArticle.model_validate(insider_article).event is None


def test_event_while_the_facts_are_still_being_read() -> None:
    # The row carries the type first: no facts yet, and `verified` is false.
    event = CorporateEvent.model_validate(
        {
            "type": "offering",
            "stage": None,
            "role": None,
            "counterparty": None,
            "facts": [],
            "verified": False,
            "also": [],
        }
    )
    assert event.type is CorporateEventType.OFFERING
    assert event.facts == []
    assert event.verified is False
    assert (event.stage, event.role, event.counterparty) == (None, None, None)


def test_fact_range_and_scale() -> None:
    # The two shapes the API reference gives for a range and a scaled figure.
    low_high = CorporateEventFact.model_validate(
        {
            "name": "new_value",
            "value": "$6.50 to $6.90",
            "number": 6.5,
            "number_high": 6.9,
            "unit": "USD",
            "scale": None,
        }
    )
    assert (low_high.number, low_high.number_high) == (6.5, 6.9)
    scaled = CorporateEventFact.model_validate(
        {
            "name": "deal_value",
            "value": "$340 million",
            "number": 340,
            "number_high": None,
            "unit": "USD",
            "scale": "millions",
        }
    )
    # A whole JSON number still lands as a float, like KeyMetric.numeric.
    assert scaled.number == 340.0
    assert isinstance(scaled.number, float)
    assert scaled.scale == "millions"


def test_unknown_event_type_passes_through_as_str() -> None:
    event = CorporateEvent.model_validate(
        {
            "type": "spin_off",
            "facts": [],
            "verified": True,
            "also": [{"type": "tender_offer", "facts": []}],
            "future_field": 1,
        }
    )
    assert event.type == "spin_off"
    assert not isinstance(event.type, CorporateEventType)
    assert event.also[0].type == "tender_offer"
    assert event.model_extra == {"future_field": 1}


def test_event_type_enum_matches_the_api_vocabulary() -> None:
    # The unknown-type 400 lists every allowed value, in the API's own order.
    msg = load("event_type_unknown_400")["body"]["extra"]["fields"][0]["msg"]
    allowed = msg.split("Allowed: ", 1)[1].split(", ")
    assert [member.value for member in CorporateEventType] == allowed
    assert len(allowed) == 17


# --- the two 400s ----------------------------------------------------------


def _mock_400(name: str) -> dict[str, Any]:
    recorded = load(name)
    respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(recorded["status"], json=recorded["body"])
    )
    return recorded["body"]


@respx.mock
def test_unknown_event_type_is_a_bad_request(client: Client) -> None:
    # A rejected parameter: the validator entry names it in `loc`.
    body = _mock_400("event_type_unknown_400")
    with pytest.raises(BadRequestError) as exc:
        client.news.list(event_type="bogus")
    err = exc.value
    assert err.status == 400
    assert err.message == "Validation error"
    assert err.body == body
    assert list(err.fields) == ["event_type"]
    (msg,) = err.fields["event_type"]
    assert msg.startswith("Value error, unknown event_type: bogus. Allowed: earnings, ")
    assert msg.endswith("clinical_regulatory, other")
    assert "event_type" in err.allowed_params
    assert err.extra["docs"] == "https://alphai.io/developers"


@respx.mock
def test_event_type_with_sort_ingested_is_a_bad_request(client: Client) -> None:
    # A rule across two parameters: `loc` is empty, so the message is filed
    # under "_" rather than under either parameter.
    _mock_400("event_type_sort_ingested_400")
    with pytest.raises(BadRequestError) as exc:
        client.news.list(event_type="buyback", sort="ingested")
    err = exc.value
    assert err.status == 400
    assert err.message == "Validation error"
    assert list(err.fields) == ["_"]
    (msg,) = err.fields["_"]
    assert msg.startswith("Value error, event_type cannot be combined with sort=ingested")
    assert "Poll sort=published with from_date and de-duplicate by uid." in msg
    assert {"event_type", "sort"} <= set(err.allowed_params)


@respx.mock
def test_event_type_400_is_not_retried(client: Client) -> None:
    recorded = load("event_type_sort_ingested_400")
    route = respx.get(f"{BASE_URL}/api/news/").mock(
        return_value=httpx.Response(recorded["status"], json=recorded["body"])
    )
    with pytest.raises(BadRequestError):
        list(client.news.iter(event_type="buyback", sort="ingested"))
    assert route.call_count == 1


@pytest.mark.parametrize(
    ("fixture", "key"),
    [("event_type_unknown_400", "event_type"), ("event_type_sort_ingested_400", "_")],
)
@respx.mock
async def test_async_event_type_400s(fixture: str, key: str) -> None:
    _mock_400(fixture)
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        with pytest.raises(BadRequestError) as exc:
            await client.news.list(event_type="bogus")
    assert list(exc.value.fields) == [key]
    assert "event_type" in exc.value.allowed_params
