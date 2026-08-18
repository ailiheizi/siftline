from __future__ import annotations

import hashlib
import json

from .canonical import dedup_key
from .models import Item


def _raw_fingerprint(item: Item) -> str:
    blob = json.dumps(item.raw, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def item_key(item: Item) -> str:
    """Stable dedup identity: canonical URL when present, else raw fingerprint."""
    if item.url:
        return dedup_key(item.url)
    if item.raw:
        return _raw_fingerprint(item)
    return hashlib.sha256((item.source or "").encode("utf-8")).hexdigest()


def dedupe(items: list[Item]) -> list[Item]:
    """Return items with duplicates removed. First occurrence wins; order is stable."""
    seen: set[str] = set()
    out: list[Item] = []
    for item in items:
        key = item_key(item)
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out
