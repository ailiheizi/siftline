from __future__ import annotations

from typing import Any

from .. import http
from ..errors import ProviderHTTPError
from ..models import Item, Provenance, Result
from ..util import api_key, require_collection, truncate
from .base import BaseProvider


class TavilyProvider(BaseProvider):
    name = "tavily"

    def _execute(self, operation: str, query: str, params: dict[str, Any], query_id: str) -> Result:
        if operation != "search":
            raise ProviderHTTPError(
                "usage",
                f"unsupported tavily operation: {operation}",
                retryable=False,
                preflight=True,
            )
        settings = self.config.providers.tavily
        key = api_key(settings.api_key_env, ("TAVILY_API_KEY",))
        if not key:
            raise ProviderHTTPError(
                "auth",
                f"Tavily API key missing; set {settings.api_key_env} or TAVILY_API_KEY",
                retryable=False,
                preflight=True,
            )
        url = f"{settings.base_url}/search"
        body = {
            "query": query,
            "max_results": int(params.get("limit", 10)),
            "include_answer": False,
            "search_depth": "basic",
        }
        data = http.post_json(
            url,
            json=body,
            headers={"Authorization": f"Bearer {key}"},
            timeout=settings.timeout_seconds,
            connect_timeout=self.config.http.connect_timeout_seconds,
            retries=self.config.http.retries,
            transport=self._http_transport,
        )
        results = require_collection(data, provider="tavily", url=url, key="results")
        items = []
        for r in results:
            items.append(
                Item(
                    url=r.get("url"),
                    title=r.get("title") or r.get("url") or "",
                    snippet=truncate(r.get("content"), 500),
                    published_at=r.get("published_date"),
                    source=r.get("url"),
                    extra={"score": r.get("score")},
                    raw={
                        k: r[k]
                        for k in ("title", "url", "content", "score", "published_date")
                        if r.get(k) is not None
                    },
                )
            )
        return Result(
            query_id=query_id,
            provider=self.name,
            operation=operation,
            query=query,
            params=params,
            items=items,
            provenance=Provenance(transport="http", source=url, engine="tavily"),
        )
