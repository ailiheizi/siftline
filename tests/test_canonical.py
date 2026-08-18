from __future__ import annotations

from siftline.canonical import canonical_url, dedup_key, github_repo_url, normalize_items
from siftline.models import Item


def test_github_repo_url_forms() -> None:
    assert github_repo_url("git@github.com:user/repo.git") == "https://github.com/user/repo"
    assert github_repo_url("ssh://git@github.com/user/repo.git") == "https://github.com/user/repo"
    assert github_repo_url("git+https://github.com/user/repo.git") == "https://github.com/user/repo"
    assert github_repo_url("https://github.com/user/repo") == "https://github.com/user/repo"
    assert github_repo_url("https://github.com/user/repo/") == "https://github.com/user/repo"
    assert github_repo_url("https://gitlab.com/user/repo") is None
    assert github_repo_url("https://github.com/useronly") is None


def test_canonical_url() -> None:
    assert canonical_url("HTTPS://GitHub.com/User/Repo/") == "https://github.com/User/Repo"
    assert canonical_url("http://example.com:80/a/b") == "http://example.com/a/b"
    assert canonical_url("https://example.com:443/x/") == "https://example.com/x"
    assert canonical_url("https://example.com:8080/x/") == "https://example.com:8080/x"
    assert canonical_url("  https://example.com/a  ") == "https://example.com/a"


def test_dedup_key_lowercases_and_strips_fragment() -> None:
    assert dedup_key("https://GitHub.com/User/Repo#readme") == "https://github.com/user/repo"
    assert dedup_key("https://example.com/x") == dedup_key("https://EXAMPLE.com/x/")
    assert dedup_key("not-a-url") == "not-a-url"


def test_normalize_items() -> None:
    items = normalize_items([Item(url="HTTPS://GITHUB.COM/A/B/", title="x")])
    assert items[0].url == "https://github.com/A/B"
