from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1"


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ErrorItem(BaseModel):
    """A classified, machine-readable error or warning attached to a Result."""

    code: str
    message: str
    provider: str
    operation: str | None = None
    severity: str = "error"  # "error" | "warning"
    retryable: bool = False
    status_code: int | None = None
    cause: str | None = None


class Item(BaseModel):
    """A normalized search/fetch result.

    `raw` keeps the provider payload so the caller can re-derive facts without
    re-fetching. `extra` holds operation-specific structured fields.
    """

    id: str | None = None
    url: str | None = None
    title: str | None = None
    snippet: str | None = None
    published_at: str | None = None
    source: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)
    raw: dict[str, Any] = Field(default_factory=dict)


class Provenance(BaseModel):
    """Where this result came from, so a skill can reproduce it."""

    transport: str = "http"  # "gh_cli" | "http"
    source: str | None = None  # transport URL or endpoint
    cache: str = "miss"  # "hit" | "miss" | "disabled"
    elapsed_ms: int = 0
    canonical_url: str | None = None
    engine: str | None = None


class Result(BaseModel):
    """The unified, schema-versioned envelope every operation returns."""

    schema_version: str = SCHEMA_VERSION
    query_id: str
    provider: str
    operation: str
    query: str
    params: dict[str, Any] = Field(default_factory=dict)
    meta: dict[str, Any] = Field(default_factory=dict)
    retrieved_at: str = Field(default_factory=utc_now)
    items: list[Item] = Field(default_factory=list)
    errors: list[ErrorItem] = Field(default_factory=list)
    provenance: Provenance

    def has_hard_errors(self) -> bool:
        return any(e.severity == "error" for e in self.errors)
