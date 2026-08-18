from __future__ import annotations

from typing import Any

from .. import http
from ..errors import ProviderHTTPError
from ..models import Item, Provenance, Result
from ..util import require_collection, require_object, truncate
from .base import BaseProvider


def _hit_item(h: dict[str, Any]) -> Item:
    oid = str(h.get("objectID") or h.get("id") or "")
    url = h.get("url") or f"https://news.ycombinator.com/item?id={oid}"
    body = h.get("story_text") or h.get("comment_text") or h.get("text") or ""
    title = h.get("title") or h.get("story_title") or ""
    if not title:
        title = truncate(body.strip(), 200)
    snippet = truncate(body.strip(), 500)
    extra = {
        k: h[k]
        for k in (
            "author",
            "points",
            "num_comments",
            "story_id",
            "created_at_i",
            "tags",
            "parent_id",
            "type",
        )
        if h.get(k) is not None
    }
    raw = {
        k: h[k]
        for k in (
            "objectID",
            "id",
            "type",
            "title",
            "story_title",
            "url",
            "author",
            "points",
            "num_comments",
            "created_at",
            "created_at_i",
            "text",
        )
        if h.get(k) is not None
    }
    return Item(
        id=oid,
        url=url,
        title=title,
        snippet=snippet,
        published_at=h.get("created_at"),
        source=oid,
        extra=extra,
        raw=raw,
    )


class HNProvider(BaseProvider):
    name = "hn"

    def _execute(self, operation: str, query: str, params: dict[str, Any], query_id: str) -> Result:
        settings = self.config.providers.hn
        connect = self.config.http.connect_timeout_seconds
        retries = self.config.http.retries
        if operation == "search":
            url = f"{settings.base_url}/search"
            req = {"query": query, "hitsPerPage": int(params.get("limit", 10))}
            tags = params.get("tags")
            if tags:
                req["tags"] = tags
            data = http.get_json(
                url,
                params=req,
                timeout=settings.timeout_seconds,
                connect_timeout=connect,
                retries=retries,
                transport=self._http_transport,
            )
            items = [
                _hit_item(h) for h in require_collection(data, provider="hn", url=url, key="hits")
            ]
            meta = {
                k: data[k]
                for k in ("nbHits", "page", "nbPages", "hitsPerPage", "processingTimeMS")
                if data.get(k) is not None
            }
            return Result(
                query_id=query_id,
                provider=self.name,
                operation=operation,
                query=query,
                params=params,
                items=items,
                meta=meta,
                provenance=Provenance(transport="http", source=url, engine="algolia"),
            )
        if operation == "item":
            item_id = str(params.get("id") or query)
            url = f"{settings.base_url}/items/{item_id}"
            data = require_object(
                http.get_json(
                    url,
                    timeout=settings.timeout_seconds,
                    connect_timeout=connect,
                    retries=retries,
                    transport=self._http_transport,
                ),
                provider="hn",
                url=url,
            )
            return Result(
                query_id=query_id,
                provider=self.name,
                operation=operation,
                query=query,
                params=params,
                items=[_hit_item(data)],
                provenance=Provenance(transport="http", source=url, engine="algolia"),
            )
        raise ProviderHTTPError(
            "usage", f"unsupported hn operation: {operation}", retryable=False, preflight=True
        )
