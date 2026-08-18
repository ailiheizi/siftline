from __future__ import annotations

import os
from typing import Any

from .errors import ProviderHTTPError


def api_key(primary_env: str, fallback_envs: tuple[str, ...] = ()) -> str | None:
    for name in (primary_env, *fallback_envs):
        value = os.environ.get(name)
        if value:
            return value
    return None


def truncate(text: str | None, limit: int, suffix: str = "\u2026") -> str:
    if not text:
        return ""
    value = str(text)
    if len(value) <= limit:
        return value
    return value[: max(0, limit - len(suffix))] + suffix


def _require_object_list(data: Any, *, provider: str, url: str) -> list[dict[str, Any]]:
    if not isinstance(data, list):
        raise ProviderHTTPError(
            "parse",
            f"{url} returned a non-list payload; cannot normalize",
            retryable=False,
            provider=provider,
        )
    for index, element in enumerate(data):
        if not isinstance(element, dict):
            raise ProviderHTTPError(
                "parse",
                f"{url} returned a non-object element at [{index}]",
                retryable=False,
                provider=provider,
            )
    return data


def require_object(data: Any, *, provider: str, url: str) -> dict[str, Any]:
    """Require a decoded JSON payload to be a JSON object.

    A successful transport that returned a payload the provider cannot normalize
    becomes a ``parse`` error (``postprocess_failed`` in the ledger, provider was
    called) instead of an ambiguous internal failure.
    """
    if not isinstance(data, dict):
        raise ProviderHTTPError(
            "parse",
            f"{url} returned a non-object payload; cannot normalize",
            retryable=False,
            provider=provider,
        )
    return data


def require_collection(data: Any, *, provider: str, url: str, key: str) -> list[dict[str, Any]]:
    """Require a JSON object whose named field is a list of JSON objects.

    Bounded response-shape validation for collection paths: the top-level object
    plus the expected result array with object elements. A malformed shape raises
    ``ProviderHTTPError`` code ``parse`` rather than leaking an attribute error
    into an ambiguous internal failure.
    """
    obj = require_object(data, provider=provider, url=url)
    collection = obj.get(key, [])
    if not isinstance(collection, list):
        raise ProviderHTTPError(
            "parse",
            f"{url} returned a non-list '{key}' collection",
            retryable=False,
            provider=provider,
        )
    for index, element in enumerate(collection):
        if not isinstance(element, dict):
            raise ProviderHTTPError(
                "parse",
                f"{url} returned a non-object element at {key}[{index}]",
                retryable=False,
                provider=provider,
            )
    return collection


def require_object_list(data: Any, *, provider: str, url: str) -> list[dict[str, Any]]:
    """Require a top-level JSON array of JSON objects (list endpoints)."""
    return _require_object_list(data, provider=provider, url=url)
