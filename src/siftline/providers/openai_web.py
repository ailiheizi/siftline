from __future__ import annotations

from typing import Any

from .. import http
from ..canonical import dedup_key
from ..errors import ProviderHTTPError
from ..models import Item, Provenance, Result
from ..util import api_key, truncate
from .base import BaseProvider

_SNIPPET_KEYS = ("description", "snippet", "content", "snippet_fragment", "text")


def _collect_web_results(payload: Any) -> tuple[list[Item], dict[str, Any]]:
    """Walk the Responses API payload for anything shaped like a web result.

    Deliberately generic so any OpenAI-compatible provider works without
    hardcoding one vendor's exact response shape.
    """
    items: list[Item] = []
    usage: dict[str, Any] = {}
    seen: set[str] = set()

    def walk(node: Any, depth: int) -> None:
        nonlocal usage
        if depth > 12 or node is None:
            return
        if isinstance(node, dict):
            if node.get("usage") and isinstance(node["usage"], dict):
                usage = node["usage"]
            for value in node.values():
                walk(value, depth + 1)
            url = node.get("url")
            title = node.get("title") or node.get("name")
            if isinstance(url, str) and url and isinstance(title, str) and title:
                key = dedup_key(url)
                if key in seen:
                    return
                seen.add(key)
                snippet = ""
                for name in _SNIPPET_KEYS:
                    candidate = node.get(name)
                    if isinstance(candidate, str) and candidate:
                        snippet = truncate(candidate, 600)
                        break
                published = (
                    node.get("publishedAt")
                    or node.get("published_date")
                    or node.get("date")
                    or node.get("published")
                )
                items.append(
                    Item(
                        url=url,
                        title=title,
                        snippet=snippet,
                        published_at=published,
                        source=url,
                        extra={"score": node.get("score")},
                        raw={
                            k: node[k]
                            for k in ("url", "title", "description")
                            if node.get(k) is not None
                        },
                    )
                )
        elif isinstance(node, list):
            for item in node:
                walk(item, depth + 1)

    walk(payload, 0)
    return items, usage


class OpenAIWebProvider(BaseProvider):
    name = "web"

    def _execute(self, operation: str, query: str, params: dict[str, Any], query_id: str) -> Result:
        if operation != "search":
            raise ProviderHTTPError(
                "usage",
                f"unsupported web operation: {operation}",
                retryable=False,
                preflight=True,
            )
        settings = self.config.providers.openai_web
        key = api_key(settings.api_key_env, ("OPENAI_API_KEY",))
        if not key:
            raise ProviderHTTPError(
                "auth",
                f"OpenAI-compatible API key missing; set {settings.api_key_env} or OPENAI_API_KEY",
                retryable=False,
                preflight=True,
            )
        endpoint = settings.endpoint or f"{settings.base_url.rstrip('/')}/responses"
        model = settings.model or "gpt-4o-mini"
        body = {
            "model": model,
            "input": [{"role": "user", "content": query}],
            "tools": [{"type": "web_search"}],
        }
        data = http.post_json(
            endpoint,
            json=body,
            headers={"Authorization": f"Bearer {key}"},
            timeout=settings.timeout_seconds,
            connect_timeout=self.config.http.connect_timeout_seconds,
            retries=self.config.http.retries,
            transport=self._http_transport,
        )
        if not isinstance(data, dict):
            raise ProviderHTTPError(
                "parse",
                f"{endpoint} returned a non-object payload; cannot normalize",
                retryable=False,
                provider="web",
            )
        items, usage = _collect_web_results(data)
        meta: dict[str, Any] = {"model": data.get("model")}
        if usage:
            meta["usage"] = usage
        return Result(
            query_id=query_id,
            provider=self.name,
            operation=operation,
            query=query,
            params=params,
            items=items,
            meta=meta,
            provenance=Provenance(
                transport="http", source=endpoint, engine="openai_responses_web_search"
            ),
        )
