from __future__ import annotations

from siftline.dedup import dedupe
from siftline.models import Item


def test_dedupe_by_url_case_insensitive() -> None:
    items = [
        Item(url="https://GitHub.com/user/repo", title="first"),
        Item(url="https://github.com/user/repo/", title="second"),
    ]
    out = dedupe(items)
    assert len(out) == 1
    assert out[0].title == "first"


def test_dedupe_preserves_order() -> None:
    items = [
        Item(url="https://a.example/1"),
        Item(url="https://b.example/2"),
        Item(url="https://a.example/1"),
    ]
    assert [i.url for i in dedupe(items)] == ["https://a.example/1", "https://b.example/2"]


def test_dedupe_by_raw_fingerprint_when_no_url() -> None:
    items = [
        Item(title="a", raw={"x": 1}),
        Item(title="b", raw={"x": 1}),
        Item(title="c", raw={"y": 2}),
    ]
    out = dedupe(items)
    assert len(out) == 2
    assert out[0].title == "a"
    assert out[1].title == "c"
