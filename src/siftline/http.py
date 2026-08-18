from __future__ import annotations

import json as _json
from typing import Any

import httpx

from .errors import ProviderHTTPError


def _snippet(resp: httpx.Response) -> str:
    return (resp.text or "")[:200]


def _parse(resp: httpx.Response, url: str) -> Any:
    ctype = resp.headers.get("content-type", "")
    text = resp.text or ""
    if "json" in ctype or text.lstrip().startswith(("{", "[")):
        try:
            return resp.json()
        except _json.JSONDecodeError as exc:
            raise ProviderHTTPError(
                "parse", f"invalid JSON from {url}", status_code=resp.status_code, provider="http"
            ) from exc
    return text


def _classify_status(method: str, url: str, status: int, body: str) -> ProviderHTTPError:
    lowered = body.lower()
    if status == 401:
        return ProviderHTTPError(
            "auth", f"{method} {url} returned 401 (unauthorized)", status_code=status
        )
    if status == 403:
        if "rate" in lowered:
            return ProviderHTTPError(
                "rate_limit",
                f"{method} {url} returned 403 (rate limited)",
                status_code=status,
                retryable=True,
            )
        return ProviderHTTPError(
            "auth", f"{method} {url} returned 403 (forbidden)", status_code=status
        )
    if status == 404:
        return ProviderHTTPError("not_found", f"{method} {url} returned 404", status_code=status)
    if status == 429:
        return ProviderHTTPError(
            "rate_limit",
            f"{method} {url} returned 429 (rate limited)",
            status_code=status,
            retryable=True,
        )
    if 500 <= status < 600:
        return ProviderHTTPError(
            "http", f"{method} {url} returned HTTP {status}", status_code=status, retryable=True
        )
    return ProviderHTTPError("http", f"{method} {url} returned HTTP {status}", status_code=status)


def get_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    connect_timeout: float = 10.0,
    retries: int = 1,
    transport: httpx.BaseTransport | None = None,
) -> Any:
    return _request(
        "GET",
        url,
        params=params,
        headers=headers,
        timeout=timeout,
        connect_timeout=connect_timeout,
        retries=retries,
        transport=transport,
    )


def post_json(
    url: str,
    *,
    params: dict[str, Any] | None = None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
    connect_timeout: float = 10.0,
    retries: int = 1,
    transport: httpx.BaseTransport | None = None,
) -> Any:
    return _request(
        "POST",
        url,
        params=params,
        json=json,
        headers=headers,
        timeout=timeout,
        connect_timeout=connect_timeout,
        retries=retries,
        transport=transport,
    )


def _request(
    method: str,
    url: str,
    *,
    params: dict[str, Any] | None,
    json: dict[str, Any] | None = None,
    headers: dict[str, str] | None,
    timeout: float,
    connect_timeout: float,
    retries: int,
    transport: httpx.BaseTransport | None,
) -> Any:
    timeout_obj = httpx.Timeout(timeout, connect=connect_timeout)
    for attempt in range(max(1, int(retries) + 1)):
        try:
            with httpx.Client(
                timeout=timeout_obj, headers=headers, follow_redirects=True, transport=transport
            ) as client:
                resp = client.request(method, url, params=params, json=json)
            if resp.status_code >= 400:
                raise _classify_status(method, url, resp.status_code, _snippet(resp))
            return _parse(resp, url)
        except ProviderHTTPError:
            raise
        except httpx.TimeoutException as exc:
            if attempt < int(retries):
                continue
            raise ProviderHTTPError(
                "timeout",
                f"{method} {url} timed out",
                retryable=True,
                cause=str(exc),
                provider="http",
            ) from exc
        except httpx.RequestError as exc:
            if attempt < int(retries):
                continue
            raise ProviderHTTPError(
                "transport",
                f"{method} {url} failed: {exc}",
                retryable=True,
                cause=str(exc),
                provider="http",
            ) from exc
    raise ProviderHTTPError("transport", f"{method} {url} failed", retryable=True, provider="http")
