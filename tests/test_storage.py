from __future__ import annotations

from siftline.models import Item, Provenance, Result
from siftline.storage import Storage


def _result(query_id: str = "q1") -> Result:
    return Result(
        query_id=query_id,
        provider="hn",
        operation="search",
        query="llm",
        params={"limit": 3},
        items=[Item(url="https://example.com/a", title="a")],
        provenance=Provenance(transport="http"),
    )


def test_cache_roundtrip(tmp_path) -> None:
    store = Storage(path=tmp_path / "c.db", ttl_seconds=3600)
    key = store.cache_key("hn", "search", "llm", {"limit": 3})
    assert store.cache_get(key) is None
    store.cache_set(key, _result())
    cached = store.cache_get(key)
    assert cached is not None
    assert cached.items[0].url == "https://example.com/a"
    assert cached.provenance.cache == "miss"
    store.close()


def test_cache_expiry(tmp_path) -> None:
    store = Storage(path=tmp_path / "c.db", ttl_seconds=1)
    key = store.cache_key("hn", "search", "llm", {"limit": 3})
    result = _result()
    result.retrieved_at = "2000-01-01T00:00:00Z"
    store.cache_set(key, result)
    assert store.cache_get(key) is None
    store.close()


def test_cache_disabled(tmp_path) -> None:
    store = Storage(path=tmp_path / "c.db", ttl_seconds=3600, enabled=False)
    key = store.cache_key("hn", "search", "llm", {"limit": 3})
    store.cache_set(key, _result())
    assert store.cache_get(key) is None
    store.close()


def test_cache_key_differs_on_params(tmp_path) -> None:
    store = Storage(path=tmp_path / "c.db", ttl_seconds=3600)
    a = store.cache_key("hn", "search", "llm", {"limit": 3})
    b = store.cache_key("hn", "search", "llm", {"limit": 5})
    c = store.cache_key("hn", "search", "llm", {"limit": 3})
    assert a != b
    assert a == c
    store.close()


def test_query_log_append_and_read(tmp_path) -> None:
    store = Storage(path=tmp_path / "c.db", ttl_seconds=3600)
    store.log_append(
        {
            "query_id": "q1",
            "provider": "hn",
            "operation": "search",
            "query": "llm",
            "params": {"limit": 3},
            "cache": "miss",
            "ttl": 3600,
            "elapsed_ms": 12,
            "item_count": 1,
            "error_count": 0,
        }
    )
    store.log_append(
        {
            "query_id": "q2",
            "provider": "github",
            "operation": "repo",
            "query": "a/b",
            "params": {},
            "cache": "hit",
            "ttl": 3600,
            "elapsed_ms": 0,
            "item_count": 1,
            "error_count": 0,
        }
    )
    entries = store.log_entries(limit=10)
    assert len(entries) == 2
    assert entries[0]["query_id"] == "q2"  # newest first
    assert entries[0]["params"] == {}
    assert entries[1]["provider"] == "hn"
    assert len(store.log_entries(limit=1)) == 1
    store.close()


def test_clear(tmp_path) -> None:
    store = Storage(path=tmp_path / "c.db", ttl_seconds=3600)
    key = store.cache_key("hn", "search", "llm", {"limit": 3})
    store.cache_set(key, _result())
    store.log_append(
        {
            "query_id": "q",
            "provider": "hn",
            "operation": "search",
            "query": "x",
            "params": {},
            "cache": "miss",
            "ttl": 3600,
            "elapsed_ms": 1,
            "item_count": 0,
            "error_count": 0,
        }
    )
    removed = store.clear()
    assert removed["cache_removed"] == 1
    assert removed["log_removed"] == 1
    stats = store.stats()
    assert stats["cache_entries"] == 0
    assert stats["log_entries"] == 0
    store.close()
