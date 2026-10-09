"""``client.stories`` — the story endpoints (``GET /api/stories/*``)."""

from __future__ import annotations

import httpx
import pytest
import respx

from alphai import (
    AsyncClient,
    Client,
    NotFoundError,
    PermissionDeniedError,
    Story,
    StoryCard,
    StoryLookup,
    TopStories,
)

from .conftest import BASE_URL, load

STORY_ID = "e58bf00bbc0d44ca"


@respx.mock
def test_top_parses_cards(client: Client) -> None:
    route = respx.get(f"{BASE_URL}/api/stories/top/").mock(
        return_value=httpx.Response(200, json=load("stories_top"))
    )
    top = client.stories.top()
    assert route.called
    assert isinstance(top, TopStories)
    assert top.ranking_version == 1
    assert top.as_of.tzinfo is not None
    lead = top.results[0]
    assert isinstance(lead, StoryCard)
    assert lead.story_id == STORY_ID
    assert lead.importance >= 7 and lead.publishers >= 2
    assert lead.summary_state in {"published", "stale", "preparing"}
    assert lead.updated_at is not None


@respx.mock
def test_list_sends_page_params_and_iter_follows_cursor(client: Client) -> None:
    page = load("stories_page")
    last = {"results": page["results"][:1], "next_cursor": None}
    route = respx.get(f"{BASE_URL}/api/stories/").mock(
        side_effect=[httpx.Response(200, json=page), httpx.Response(200, json=last)]
    )
    first = client.stories.list(page_size=2)
    assert len(first.results) == 2 and first.next_cursor
    assert route.calls[0].request.url.params["page_size"] == "2"
    assert "cursor" not in route.calls[0].request.url.params

    route.side_effect = [httpx.Response(200, json=page), httpx.Response(200, json=last)]
    cards = list(client.stories.iter(page_size=2))
    assert [c.story_id for c in cards] == [c["story_id"] for c in page["results"]] + [
        page["results"][0]["story_id"]
    ]
    assert route.calls[-1].request.url.params["cursor"] == page["next_cursor"]


def test_page_size_is_validated_locally(client: Client) -> None:
    with pytest.raises(ValueError):
        client.stories.list(page_size=0)
    with pytest.raises(ValueError):
        client.stories.materials(STORY_ID, page_size=51)
    with pytest.raises(ValueError):
        client.stories.get("../etc")


@respx.mock
def test_get_found_story(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/stories/{STORY_ID}/").mock(
        return_value=httpx.Response(200, json=load("story"))
    )
    lookup = client.stories.get(STORY_ID)
    assert isinstance(lookup, StoryLookup)
    assert lookup.status == "found" and lookup.redirect_to is None and lookup.article is None
    story = lookup.story
    assert isinstance(story, Story)
    assert story.story_id == STORY_ID
    assert story.key_facts and story.key_facts[0].publisher and story.key_facts[0].source_uid
    assert {t.impact for t in story.ticker_takes} <= {"positive", "negative", "neutral"}
    assert story.based_on <= story.materials_at_build
    assert story.model and story.revision_generated_at is not None
    assert "raw_text" not in story.model_dump_json()


@respx.mock
def test_get_story_follows_merges_and_returns_none_for_articles(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/stories/aaaaaaaaaaaaaaaa/").mock(
        return_value=httpx.Response(200, json={"status": "merged", "redirect_to": STORY_ID})
    )
    respx.get(f"{BASE_URL}/api/stories/{STORY_ID}/").mock(
        return_value=httpx.Response(200, json=load("story"))
    )
    lone_uid = "bbbbbbbbbbbbbbbb"
    lone = {
        "status": "not_a_story",
        "article": {"uid": lone_uid, "title": "Lone", "time_published": "2026-10-09T06:00:00Z"},
    }
    respx.get(f"{BASE_URL}/api/stories/{lone_uid}/").mock(
        return_value=httpx.Response(200, json=lone)
    )

    story = client.stories.get_story("aaaaaaaaaaaaaaaa")
    assert story is not None and story.story_id == STORY_ID
    assert client.stories.get_story("bbbbbbbbbbbbbbbb") is None
    lookup = client.stories.get("bbbbbbbbbbbbbbbb")
    assert lookup.status == "not_a_story" and lookup.article is not None
    assert lookup.article.uid == "bbbbbbbbbbbbbbbb"


@respx.mock
def test_materials_and_iter_materials(client: Client) -> None:
    page = load("story_materials")
    last = {"story_id": STORY_ID, "results": page["results"][:1], "next_cursor": None}
    route = respx.get(f"{BASE_URL}/api/stories/{STORY_ID}/materials/").mock(
        side_effect=[httpx.Response(200, json=page), httpx.Response(200, json=last)]
    )
    first = client.stories.materials(STORY_ID, page_size=3)
    assert first.story_id == STORY_ID and len(first.results) == 3
    assert all(m.uid and m.publisher and m.url for m in first.results)
    assert first.results[0].time_published <= first.results[-1].time_published, "oldest first"

    route.side_effect = [httpx.Response(200, json=page), httpx.Response(200, json=last)]
    uids = [m.uid for m in client.stories.iter_materials(STORY_ID, page_size=3)]
    assert len(uids) == 4
    assert route.calls[-1].request.url.params["cursor"] == page["next_cursor"]


@respx.mock
def test_unknown_id_and_archive_horizon(client: Client) -> None:
    respx.get(f"{BASE_URL}/api/stories/0000000000000000/").mock(
        return_value=httpx.Response(404, json={"message": "Story 0000000000000000 not found"})
    )
    with pytest.raises(NotFoundError):
        client.stories.get("0000000000000000")
    respx.get(f"{BASE_URL}/api/stories/").mock(
        return_value=httpx.Response(
            403,
            json={
                "message": "Archive horizon exceeded.",
                "extra": {"reason": "archive_horizon", "tier": "free", "archive_days": 30},
            },
        )
    )
    with pytest.raises(PermissionDeniedError):
        client.stories.list(cursor="deep")


@respx.mock
async def test_async_stories() -> None:
    respx.get(f"{BASE_URL}/api/stories/top/").mock(
        return_value=httpx.Response(200, json=load("stories_top"))
    )
    respx.get(f"{BASE_URL}/api/stories/{STORY_ID}/").mock(
        return_value=httpx.Response(200, json=load("story"))
    )
    materials = load("story_materials")
    materials["next_cursor"] = None
    respx.get(f"{BASE_URL}/api/stories/{STORY_ID}/materials/").mock(
        return_value=httpx.Response(200, json=materials)
    )
    async with AsyncClient(api_key="ak_live_test", base_url=BASE_URL) as client:
        top = await client.stories.top()
        assert top.results[0].story_id == STORY_ID
        story = await client.stories.get_story(STORY_ID)
        assert story is not None and story.why_it_matters
        uids = [m.uid async for m in client.stories.iter_materials(STORY_ID)]
        assert len(uids) == 3
