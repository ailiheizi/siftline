from __future__ import annotations

import json
import subprocess
from collections.abc import Callable
from typing import Any

import pytest

from siftline.providers.github import GithubProvider


def _runner(payload: Any, returncode: int = 0, stderr: str = "") -> Callable:
    if not isinstance(payload, str):
        payload = json.dumps(payload)

    def runner(args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(args, returncode, stdout=payload, stderr=stderr)

    return runner


@pytest.fixture
def gh_provider(config, storage) -> GithubProvider:
    return GithubProvider(config, storage)


_SEARCH_REPOS = {
    "total_count": 1,
    "items": [
        {
            "id": 1,
            "name": "repo",
            "full_name": "owner/repo",
            "html_url": "https://github.com/owner/repo",
            "description": "desc",
            "stargazers_count": 42,
            "forks_count": 3,
            "language": "Python",
            "license": {"spdx_id": "MIT"},
            "created_at": "2020-01-01T00:00:00Z",
            "updated_at": "2021-01-01T00:00:00Z",
            "archived": False,
            "fork": False,
            "topics": ["cli"],
            "default_branch": "main",
        }
    ],
}


def test_search_repos_success(gh_provider) -> None:
    calls = []
    original = gh_provider._runner

    def runner(args, **kwargs):
        calls.append(args)
        if original is None:
            return _runner(_SEARCH_REPOS)(args, **kwargs)
        return original(args, **kwargs)

    gh_provider._runner = runner
    result = gh_provider.run("search_repos", "siftline", {"limit": 5}, "q1")
    assert result.provider == "github"
    assert result.query_id == "q1"
    assert len(result.items) == 1
    item = result.items[0]
    assert item.title == "owner/repo"
    assert item.url == "https://github.com/owner/repo"
    assert item.extra["stars"] == 42
    assert item.extra["license"] == "MIT"
    assert result.provenance.transport == "gh_cli"
    assert not result.has_hard_errors()
    assert any("search/repositories" in str(a) for a in calls)


def test_cache_hit_second_run(gh_provider) -> None:
    gh_provider._runner = _runner(_SEARCH_REPOS)
    first = gh_provider.run("search_repos", "siftline", {"limit": 5}, "q1")
    assert first.provenance.cache == "miss"
    second = gh_provider.run("search_repos", "siftline", {"limit": 5}, "q1")
    assert second.provenance.cache == "hit"
    assert len(second.items) == 1


def test_error_not_cached(gh_provider) -> None:
    gh_provider._runner = _runner({}, returncode=1, stderr="gh: HTTP 404: not found")
    result = gh_provider.run("search_repos", "nope", {"limit": 5}, "q1")
    assert result.has_hard_errors()
    assert result.errors[0].code == "not_found"
    assert not result.errors[0].retryable
    key = gh_provider.storage.cache_key("github", "search_repos", "nope", {"limit": 5})
    assert gh_provider.storage.cache_get(key) is None


def test_auth_error_classified(gh_provider) -> None:
    gh_provider._runner = _runner({}, returncode=1, stderr="gh: HTTP 401: Bad credentials")
    result = gh_provider.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "auth"


def test_rate_limit_classified(gh_provider) -> None:
    gh_provider._runner = _runner({}, returncode=1, stderr="gh: HTTP 429: rate limit exceeded")
    result = gh_provider.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "rate_limit"
    assert result.errors[0].retryable


def test_not_available_when_gh_missing(gh_provider, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("siftline.providers.github.shutil.which", lambda _: None)
    result = gh_provider.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "not_available"
    assert not result.errors[0].retryable


def test_parse_error_on_non_json(gh_provider) -> None:
    gh_provider._runner = _runner("this is not json")
    result = gh_provider.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "parse"


def test_search_repos_non_list_items_is_parse(gh_provider) -> None:
    """A JSON object with a non-list 'items' collection is parse, not internal."""

    gh_provider._runner = _runner({"total_count": 1, "items": {}})
    result = gh_provider.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "parse"


def test_search_repos_non_object_element_is_parse(gh_provider) -> None:
    gh_provider._runner = _runner({"total_count": 1, "items": ["junk"]})
    result = gh_provider.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "parse"


def test_list_endpoint_object_is_parse(gh_provider) -> None:
    """A top-level object for a list endpoint is parse, not an internal failure."""

    gh_provider._runner = _runner({"error": "unexpected shape"})
    result = gh_provider.run("starred", "octocat", {"limit": 5}, "q1")
    assert result.errors[0].code == "parse"


def test_repo_non_object_is_parse(gh_provider) -> None:
    gh_provider._runner = _runner(["not", "an", "object"])
    result = gh_provider.run("repo", "o/r", {}, "q1")
    assert result.errors[0].code == "parse"


def test_search_code_normalization(gh_provider) -> None:
    payload = {
        "total_count": 1,
        "items": [
            {
                "name": "a.py",
                "path": "src/a.py",
                "sha": "abc",
                "html_url": "https://github.com/o/r/blob/main/src/a.py",
                "repository": {"full_name": "o/r"},
                "language": "Python",
                "text_matches": [{"fragment": "def x(): pass"}],
            }
        ],
    }
    gh_provider._runner = _runner(payload)
    result = gh_provider.run("search_code", "def x", {"limit": 5}, "q1")
    assert result.items[0].title == "o/r:src/a.py"
    assert result.items[0].snippet == "def x(): pass"


def test_unsupported_operation(gh_provider) -> None:
    gh_provider._runner = _runner({})
    result = gh_provider.run("totally_unknown", "x", {}, "q1")
    assert result.errors[0].code == "usage"
    assert result.errors[0].message == "unsupported github operation: totally_unknown"


def test_timeout_classified(gh_provider) -> None:
    def runner(args, **kwargs):
        raise subprocess.TimeoutExpired(" ".join(args), 5)

    gh_provider._runner = runner
    result = gh_provider.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "timeout"
    assert result.errors[0].retryable


def test_readme_decodes_base64(gh_provider) -> None:
    import base64

    content = base64.b64encode(b"# Hello\nworld").decode()
    payload = {
        "name": "README.md",
        "path": "README.md",
        "sha": "s",
        "encoding": "base64",
        "content": content,
        "html_url": "https://github.com/o/r#readme",
    }
    gh_provider._runner = _runner(payload)
    result = gh_provider.run("readme", "o/r", {}, "q1")
    assert result.items[0].title == "o/r README"
    assert "# Hello" in result.items[0].snippet


def test_tree_truncated_warning(gh_provider) -> None:
    payload = {
        "sha": "s",
        "truncated": True,
        "tree": [{"path": "a", "type": "blob", "mode": "100644", "sha": "x"}],
    }
    gh_provider._runner = _runner(payload)
    result = gh_provider.run(
        "tree", "o/r", {"branch": "main", "recursive": True, "limit": 200}, "q1"
    )
    assert result.items[0].url == "https://github.com/o/r/blob/main/a"
    assert any(e.severity == "warning" and e.code == "truncated" for e in result.errors)
