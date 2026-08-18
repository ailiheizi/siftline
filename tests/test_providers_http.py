from __future__ import annotations

import httpx
import pytest

from siftline.providers.exa import ExaProvider
from siftline.providers.hn import HNProvider
from siftline.providers.openai_web import OpenAIWebProvider
from siftline.providers.tavily import TavilyProvider


def _provider(cls, config, storage, handler):
    return cls(config, storage, http_transport=httpx.MockTransport(handler))


def _hn_search_payload() -> dict:
    return {
        "hits": [
            {
                "objectID": "123",
                "title": "Show HN: My Tool",
                "url": "https://example.com/tool",
                "author": "bob",
                "points": 15,
                "num_comments": 4,
                "created_at": "2026-01-01T00:00:00.000Z",
                "story_text": None,
            },
            {
                "objectID": "456",
                "title": None,
                "story_title": None,
                "comment_text": "   a long comment   ",
                "author": "alice",
                "points": 1,
                "num_comments": 0,
                "created_at": "2026-01-02T00:00:00.000Z",
            },
        ],
        "nbHits": 2,
        "page": 0,
        "nbPages": 1,
        "processingTimeMS": 3,
    }


def test_hn_search_maps_hits(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "hn.algolia.com"
        return httpx.Response(200, json=_hn_search_payload())

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("search", "my tool", {"limit": 10}, "q1")
    assert not result.has_hard_errors()
    assert len(result.items) == 2
    assert result.items[0].title == "Show HN: My Tool"
    assert result.items[0].url == "https://example.com/tool"
    assert result.items[0].source == "123"
    assert result.meta["nbHits"] == 2
    assert result.items[1].url == "https://news.ycombinator.com/item?id=456"
    assert result.items[1].title == "a long comment"


def test_hn_item(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "items/9" in str(request.url)
        return httpx.Response(
            200,
            json={
                "objectID": "9",
                "title": "Story",
                "url": "https://x.example",
                "author": "a",
                "created_at": "2026-01-01T00:00:00.000Z",
            },
        )

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("item", "9", {"id": 9}, "q1")
    assert result.items[0].title == "Story"


def test_hn_item_comment_shape(config, storage) -> None:
    """Algolia /items/{id} returns id/text/type, not objectID/comment_text."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "id": 9,
                "type": "comment",
                "author": "bob",
                "text": "a comment body",
                "created_at": "2026-01-01T00:00:00.000Z",
                "points": 2,
            },
        )

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("item", "9", {"id": 9}, "q1")
    item = result.items[0]
    assert item.id == "9"
    assert item.url == "https://news.ycombinator.com/item?id=9"
    assert item.title == "a comment body"
    assert item.extra["type"] == "comment"


def test_hn_second_run_is_cached(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_hn_search_payload())

    prov = _provider(HNProvider, config, storage, handler)
    first = prov.run("search", "my tool", {"limit": 10}, "q1")
    second = prov.run("search", "my tool", {"limit": 10}, "q2")
    assert first.provenance.cache == "miss"
    assert second.provenance.cache == "hit"
    assert len(second.items) == 2


def test_exa_missing_key(config, storage) -> None:
    prov = _provider(ExaProvider, config, storage, lambda r: httpx.Response(200, json={}))
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "auth"
    assert "EXA_API_KEY" in result.errors[0].message


def test_exa_success_with_key(config, storage, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIFTLINE_EXA_API_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["x-api-key"] == "secret"
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "title": "T",
                        "url": "https://ex.example/1",
                        "publishedDate": "2026-01-01",
                        "highlights": ["snippet text"],
                    }
                ]
            },
        )

    prov = _provider(ExaProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert not result.has_hard_errors()
    assert result.items[0].snippet == "snippet text"


def test_tavily_missing_key(config, storage) -> None:
    prov = _provider(TavilyProvider, config, storage, lambda r: httpx.Response(200, json={}))
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "auth"


def test_tavily_success_with_fallback_env(config, storage, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvkey")

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer tvkey"
        return httpx.Response(
            200,
            json={
                "results": [{"title": "T", "url": "https://t.example/1", "content": "body text"}]
            },
        )

    prov = _provider(TavilyProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.items[0].snippet == "body text"


def test_openai_web_missing_key(config, storage) -> None:
    prov = _provider(OpenAIWebProvider, config, storage, lambda r: httpx.Response(200, json={}))
    result = prov.run("search", "x", {}, "q1")
    assert result.errors[0].code == "auth"


def test_openai_web_collects_results(config, storage, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "okey")
    payload = {
        "id": "resp_1",
        "model": "gpt-4o-mini",
        "output": [
            {
                "type": "web_search_call",
                "id": "ws_1",
                "status": "completed",
                "output": [
                    {
                        "type": "web_search_call_result",
                        "url": "https://w.example/1",
                        "title": "First",
                        "description": "desc one",
                    }
                ],
            }
        ],
        "usage": {"total_tokens": 100},
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert "responses" in str(request.url)
        assert request.headers["Authorization"] == "Bearer okey"
        return httpx.Response(200, json=payload)

    prov = _provider(OpenAIWebProvider, config, storage, handler)
    result = prov.run("search", "question", {}, "q1")
    assert not result.has_hard_errors()
    assert len(result.items) == 1
    assert result.items[0].url == "https://w.example/1"
    assert result.meta["model"] == "gpt-4o-mini"
    assert result.meta["usage"]["total_tokens"] == 100


def test_http_error_classification(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "rate_limit"
    assert result.errors[0].retryable
    assert result.errors[0].status_code == 429


def test_http_auth_classification(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={})

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "auth"


def test_http_not_found_classification(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={})

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("item", "999999999", {"id": 999999999}, "q1")
    assert result.errors[0].code == "not_found"


def test_hn_collection_non_list_is_parse(config, storage) -> None:
    """A JSON object with a non-list collection is a parse (postprocess) failure."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": "oops"})

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "parse"


def test_hn_non_object_element_is_parse(config, storage) -> None:
    """A JSON object with a non-object element in the collection is parse."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": [{"objectID": "1"}, "junk"]})

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "parse"


def test_exa_results_shape_is_parse(config, storage, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIFTLINE_EXA_API_KEY", "secret")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": [{"title": "T"}, None]})

    prov = _provider(ExaProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "parse"


def test_tavily_results_shape_is_parse(config, storage, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TAVILY_API_KEY", "tvkey")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"results": {"nope": 1}})

    prov = _provider(TavilyProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "parse"


def test_http_timeout_retries_and_classifies(config, storage) -> None:
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        raise httpx.ConnectTimeout("no route", request=request)

    prov = _provider(HNProvider, config, storage, handler)
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "timeout"
    assert result.errors[0].retryable
    assert len(calls) == 2  # initial attempt + 1 retry


def test_unsupported_operation(config, storage) -> None:
    prov = _provider(HNProvider, config, storage, lambda r: httpx.Response(200, json={}))
    result = prov.run("not_a_thing", "x", {}, "q1")
    assert result.errors[0].code == "usage"
