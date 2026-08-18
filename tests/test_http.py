from __future__ import annotations

import json

import httpx
import pytest

from siftline import http
from siftline.errors import ProviderHTTPError


def test_get_json_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        return httpx.Response(200, json={"ok": True})

    data = http.get_json(
        "https://x.example/a",
        transport=httpx.MockTransport(handler),
        timeout=5,
        connect_timeout=5,
        retries=0,
    )
    assert data == {"ok": True}


def test_get_json_sends_query_params() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["query"] == "hello world"
        return httpx.Response(200, json={})

    http.get_json(
        "https://x.example/search",
        params={"query": "hello world"},
        transport=httpx.MockTransport(handler),
        timeout=5,
        connect_timeout=5,
        retries=0,
    )


def test_post_json_sends_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert json.loads(request.content) == {"query": "x"}
        return httpx.Response(200, json={})

    http.post_json(
        "https://x.example/search",
        json={"query": "x"},
        transport=httpx.MockTransport(handler),
        timeout=5,
        connect_timeout=5,
        retries=0,
    )


def test_non_json_response_returned_as_text() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="plain text", headers={"content-type": "text/plain"})

    data = http.get_json(
        "https://x.example/a",
        transport=httpx.MockTransport(handler),
        timeout=5,
        connect_timeout=5,
        retries=0,
    )
    assert data == "plain text"


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (401, "auth", False),
        (403, "auth", False),
        (404, "not_found", False),
        (429, "rate_limit", True),
        (500, "http", True),
        (400, "http", False),
    ],
)
def test_status_classification(status: int, code: str, retryable: bool) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(status, json={})

    with pytest.raises(ProviderHTTPError) as exc_info:
        http.get_json(
            "https://x.example/a",
            transport=httpx.MockTransport(handler),
            timeout=5,
            connect_timeout=5,
            retries=0,
        )
    assert exc_info.value.code == code
    assert exc_info.value.retryable is retryable


def test_connect_error_is_transport() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    with pytest.raises(ProviderHTTPError) as exc_info:
        http.get_json(
            "https://x.example/a",
            transport=httpx.MockTransport(handler),
            timeout=5,
            connect_timeout=5,
            retries=0,
        )
    assert exc_info.value.code == "transport"
    assert exc_info.value.retryable
