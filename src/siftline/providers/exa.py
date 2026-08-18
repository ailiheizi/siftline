from __future__ import annotations

from typing import Any

from .. import http
from ..errors import ProviderHTTPError
from ..models import Item, Provenance, Result
from ..util import api_key, require_collection, truncate
from .base import BaseProvider


class ExaProvider(BaseProvider):
    name = "exa"

    def _execute(self, operation: str, query: str, params: dict[str, Any], query_id: str) -> Result:
        if operation != "search":
            raise ProviderHTTPError(
                "usage",
                f"unsupported exa operation: {operation}",
                retryable=False,
                preflight=True,
            )
        settings = self.config.providers.exa
        key = api_key(settings.api_key_env, ("EXA_API_KEY",))
        if not key:
            raise ProviderHTTPError(
                "auth",
                f"Exa API key missing; set {settings.api_key_env} or EXA_API_KEY",
                retryable=False,
                preflight=True,
            )
        url = f"{settings.base_url}/search"
        body = {"query": query, "numResults": int(params.get("limit", 10)), "type": "auto"}
        data = http.post_json(
            url,
            json=body,
            headers={"x-api-key": key},
            timeout=settings.timeout_seconds,
            connect_timeout=self.config.http.connect_timeout_seconds,
            retries=self.config.http.retries,
            transport=self._http_transport,
        )
        results = require_collection(data, provider="exa", url=url, key="results")
        items = []
        for r in results:
            highlights = r.get("highlights") or []
            snippet = None
            if highlights:
                snippet = truncate(highlights[0], 500)
            elif r.get("text"):
                snippet = truncate(r["text"], 500)
            items.append(
                Item(
                    url=r.get("url"),
                    title=r.get("title") or r.get("url") or "",
                    snippet=snippet,
                    published_at=r.get("publishedDate"),
                    source=r.get("url"),
                    extra={"author": r.get("author"), "score": r.get("score")},
                    raw={
                        k: r[k]
                        for k in ("id", "title", "url", "publishedDate", "author", "score")
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
            provenance=Provenance(transport="http", source=url, engine="exa"),
        )
