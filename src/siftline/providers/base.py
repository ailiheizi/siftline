from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any, ClassVar

import httpx

from ..canonical import normalize_items
from ..config import Config
from ..dedup import dedupe
from ..errors import ProviderHTTPError
from ..models import Provenance, Result, utc_now
from ..storage import Storage


class BaseProvider(ABC):
    """Common run/cache/log pipeline for every provider.

    A provider implements `_execute` and gets caching, dedup, canonicalization,
    and the reproducible query log for free.
    """

    name: ClassVar[str] = ""
    transport_label: ClassVar[str] = "http"

    def __init__(
        self, config: Config, storage: Storage, http_transport: httpx.BaseTransport | None = None
    ) -> None:
        self.config = config
        self.storage = storage
        self._http_transport = http_transport

    @abstractmethod
    def _execute(self, operation: str, query: str, params: dict[str, Any], query_id: str) -> Result:
        raise NotImplementedError

    def run(self, operation: str, query: str, params: dict[str, Any], query_id: str) -> Result:
        key = self.storage.cache_key(self.name, operation, query, params)
        start = time.monotonic()
        cached = self.storage.cache_get(key)
        if cached is not None:
            cached.provenance.cache = "hit"
            cached.provenance.elapsed_ms = 0
            # A cached result returned under a new --query-id must carry the
            # current query id; the stored row still keeps its original one.
            cached.query_id = query_id
            self._record(
                query_id,
                operation,
                query,
                params,
                "hit",
                0,
                len(cached.items),
                len(cached.errors),
                outcome="cache_hit",
                provider_called=False,
                error_codes=[e.code for e in cached.errors if e.code],
            )
            return cached

        exc: ProviderHTTPError | None = None
        try:
            result = self._execute(operation, query, params, query_id)
        except ProviderHTTPError as e:
            exc = e
            result = Result(
                query_id=query_id,
                provider=self.name,
                operation=operation,
                query=query,
                params=params,
                provenance=Provenance(transport=self.transport_label),
            )
            result.errors.append(e.to_error(provider=self.name, operation=operation))

        elapsed_ms = int((time.monotonic() - start) * 1000)
        result.provenance.elapsed_ms = elapsed_ms
        result.items = normalize_items(dedupe(result.items))
        if not result.has_hard_errors():
            self.storage.cache_set(key, result)

        if exc is None:
            if result.has_hard_errors():
                # The transport returned a usable payload, but a hard downstream
                # consistency error (for example the GitHub empty_result guard)
                # means the result is not usable: this is a post-processing
                # failure, not a provider success. Warnings-only results remain
                # provider_succeeded.
                outcome, provider_called = "postprocess_failed", True
            else:
                outcome, provider_called = "provider_succeeded", True
        elif exc.preflight:
            outcome, provider_called = "validation_failed", False
        elif exc.code == "parse":
            outcome, provider_called = "postprocess_failed", True
        else:
            outcome, provider_called = "provider_failed", True

        self._record(
            query_id,
            operation,
            query,
            params,
            "miss",
            elapsed_ms,
            len(result.items),
            len(result.errors),
            outcome=outcome,
            provider_called=provider_called,
            error_codes=[e.code for e in result.errors if e.code],
        )
        return result

    def _record(
        self,
        query_id: str,
        operation: str,
        query: str,
        params: dict[str, Any],
        cache_state: str,
        elapsed_ms: int,
        item_count: int,
        error_count: int,
        *,
        outcome: str,
        provider_called: bool,
        error_codes: list[str],
    ) -> None:
        self.storage.log_append(
            {
                "ts": utc_now(),
                "query_id": query_id,
                "provider": self.name,
                "operation": operation,
                "query": query,
                "params": params,
                "cache": cache_state,
                "ttl": self.storage.ttl_seconds,
                "elapsed_ms": elapsed_ms,
                "item_count": item_count,
                "error_count": error_count,
                "outcome": outcome,
                "provider_called": provider_called,
                "error_codes": error_codes,
            }
        )
