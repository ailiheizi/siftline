from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import httpx

from ..config import Config
from ..errors import ProviderHTTPError
from ..models import ErrorItem, Item, Provenance, Result
from ..storage import Storage
from ..util import require_collection, require_object, require_object_list
from .base import BaseProvider

Runner = Callable[..., subprocess.CompletedProcess[str]]


def _subset(mapping: dict[str, Any], keys: list[str]) -> dict[str, Any]:
    return {k: mapping[k] for k in keys if mapping.get(k) is not None}


def _empty_search_guard(data: dict[str, Any], items: list[Item]) -> list[ErrorItem]:
    """GitHub search sometimes reports matches (total_count) but returns no items.

    A non-zero total with zero items is almost always a transient provider-side
    index/transport problem, not an honest empty result. Flag it so the caller
    does not confuse vocabulary failure with transport failure.
    """
    total = data.get("total_count") or 0
    if int(total) > 0 and not items:
        return [
            ErrorItem(
                code="empty_result",
                message=f"provider reported {total} matches but returned no items",
                provider="github",
                retryable=True,
            )
        ]
    return []


def _repo_item(r: dict[str, Any]) -> Item:
    full = r.get("full_name") or r.get("fullName") or ""
    lic = r.get("license")
    license_spdx = None
    if isinstance(lic, dict):
        license_spdx = lic.get("spdx_id") or lic.get("name")
    return Item(
        id=str(r.get("id") or ""),
        url=r.get("html_url") or r.get("url"),
        title=full or r.get("name") or "",
        snippet=r.get("description") or "",
        source=full,
        published_at=r.get("created_at"),
        extra={
            "stars": r.get("stargazers_count", r.get("stargazerCount")),
            "forks": r.get("forks_count", r.get("forkCount")),
            "language": r.get("language"),
            "license": license_spdx,
            "archived": r.get("archived"),
            "fork": r.get("fork"),
            "homepage": r.get("homepage", r.get("homepageUrl")),
            "updated_at": r.get("updated_at", r.get("updatedAt")),
            "default_branch": r.get("default_branch")
            or (r.get("defaultBranchRef") or {}).get("name"),
            "topics": r.get("topics", r.get("repositoryTopics", [])),
        },
        raw=_subset(
            r,
            [
                "id",
                "name",
                "full_name",
                "html_url",
                "description",
                "stargazers_count",
                "forks_count",
                "language",
                "license",
                "archived",
                "fork",
                "created_at",
                "updated_at",
                "default_branch",
            ],
        ),
    )


def _user_item(r: dict[str, Any]) -> Item:
    return Item(
        id=str(r.get("id") or ""),
        url=r.get("html_url"),
        title=r.get("login") or "",
        source=r.get("login"),
        extra={"type": r.get("type")},
        raw=_subset(r, ["login", "id", "html_url", "avatar_url", "type"]),
    )


def _code_item(r: dict[str, Any]) -> Item:
    repo = r.get("repository") or {}
    full = repo.get("full_name") or ""
    path = r.get("path") or ""
    matches = r.get("text_matches") or []
    fragment = matches[0].get("fragment", "") if matches else ""
    url = r.get("html_url")
    if not url and full and path:
        url = f"https://github.com/{full}/blob/{r.get('sha', 'HEAD')}/{path}"
    return Item(
        id=str(r.get("sha") or r.get("name") or ""),
        url=url,
        title=f"{full}:{path}" if full else path,
        snippet=fragment,
        source=f"{full}#{path}",
        extra={"language": r.get("language"), "repository": full},
        raw=_subset(r, ["name", "path", "sha", "language", "url", "html_url"]),
    )


def _tree_item(entry: dict[str, Any], owner: str, repo: str, branch: str) -> Item:
    path = entry.get("path", "")
    if entry.get("type") == "tree":
        url = f"https://github.com/{owner}/{repo}/tree/{branch}/{path}"
    else:
        url = f"https://github.com/{owner}/{repo}/blob/{branch}/{path}"
    return Item(
        url=url,
        title=path,
        snippet=entry.get("type"),
        source=f"{owner}/{repo}:{path}",
        extra={"mode": entry.get("mode"), "size": entry.get("size")},
        raw=_subset(entry, ["path", "mode", "type", "sha", "size"]),
    )


def _readme_item(r: dict[str, Any], owner: str, repo: str) -> Item:
    content = ""
    if r.get("encoding") == "base64" and r.get("content"):
        try:
            content = base64.b64decode(r["content"]).decode("utf-8", errors="replace")
        except Exception:
            content = ""
    return Item(
        id=r.get("sha"),
        url=r.get("html_url") or f"https://github.com/{owner}/{repo}#readme",
        title=f"{owner}/{repo} README",
        snippet=content[:800],
        source=f"{owner}/{repo}#readme",
        extra={"size": r.get("size"), "encoding": r.get("encoding")},
        raw=_subset(r, ["name", "path", "sha", "size", "encoding", "html_url"]),
    )


def _license_item(r: dict[str, Any], owner: str, repo: str) -> Item:
    content = ""
    if r.get("encoding") == "base64" and r.get("content"):
        try:
            content = base64.b64decode(r["content"]).decode("utf-8", errors="replace")
        except Exception:
            content = ""
    lic = r.get("license") or {}
    return Item(
        id=r.get("sha"),
        url=r.get("html_url") or f"https://github.com/{owner}/{repo}#license",
        title=f"{owner}/{repo} LICENSE ({lic.get('name') or lic.get('spdx_id') or 'unknown'})",
        snippet=content[:800],
        source=f"{owner}/{repo}#license",
        extra={"spdx_id": lic.get("spdx_id"), "key": lic.get("key"), "size": r.get("size")},
        raw=_subset(r, ["name", "path", "sha", "size", "encoding", "html_url", "license"]),
    )


class GithubProvider(BaseProvider):
    name = "github"
    transport_label = "gh_cli"

    def __init__(
        self,
        config: Config,
        storage: Storage,
        http_transport: httpx.BaseTransport | None = None,
        runner: Runner | None = None,
    ) -> None:
        super().__init__(config, storage, http_transport=http_transport)
        self._runner = runner

    def _execute(self, operation: str, query: str, params: dict[str, Any], query_id: str) -> Result:
        op = getattr(self, f"_op_{operation}", None)
        if op is None:
            raise ProviderHTTPError(
                "usage",
                f"unsupported github operation: {operation}",
                retryable=False,
                preflight=True,
            )
        out = op(query, params)
        if isinstance(out, tuple) and len(out) == 4:
            items, source, engine, warnings = out
        else:
            items, source, engine = out
            warnings = []
        return Result(
            query_id=query_id,
            provider=self.name,
            operation=operation,
            query=query,
            params=params,
            items=items,
            errors=warnings,
            provenance=Provenance(transport=self.transport_label, source=source, engine=engine),
        )

    # -- operations ----------------------------------------------------------

    def _op_search_repos(
        self, query: str, params: dict[str, Any]
    ) -> tuple[list[Item], str, str, list[ErrorItem]]:
        limit = int(params.get("limit", 10))
        data = self._gh(["search/repositories", "-f", f"q={query}", "-f", f"per_page={limit}"])
        items = [
            _repo_item(r)
            for r in require_collection(
                data,
                provider=self.name,
                url="https://api.github.com/search/repositories",
                key="items",
            )
        ]
        errors = _empty_search_guard(data, items)
        return items[:limit], "https://api.github.com/search/repositories", "github_search", errors

    def _op_search_code(
        self, query: str, params: dict[str, Any]
    ) -> tuple[list[Item], str, str, list[ErrorItem]]:
        limit = int(params.get("limit", 10))
        data = self._gh(
            [
                "search/code",
                "-H",
                "Accept: application/vnd.github.text-match+json",
                "-f",
                f"q={query}",
                "-f",
                f"per_page={limit}",
            ]
        )
        items = [
            _code_item(r)
            for r in require_collection(
                data, provider=self.name, url="https://api.github.com/search/code", key="items"
            )
        ]
        errors = _empty_search_guard(data, items)
        return items[:limit], "https://api.github.com/search/code", "github_search", errors

    def _op_repo(self, query: str, params: dict[str, Any]) -> tuple[list[Item], str, str]:
        data = require_object(
            self._gh([f"repos/{query}"]),
            provider=self.name,
            url=f"https://api.github.com/repos/{query}",
        )
        return [_repo_item(data)], f"https://github.com/{query}", "github_api"

    def _op_readme(self, query: str, params: dict[str, Any]) -> tuple[list[Item], str, str]:
        owner, repo = query.split("/", 1)
        data = require_object(
            self._gh([f"repos/{owner}/{repo}/readme"]),
            provider=self.name,
            url=f"https://api.github.com/repos/{owner}/{repo}/readme",
        )
        return [_readme_item(data, owner, repo)], f"https://github.com/{owner}/{repo}", "github_api"

    def _op_license(self, query: str, params: dict[str, Any]) -> tuple[list[Item], str, str]:
        owner, repo = query.split("/", 1)
        data = require_object(
            self._gh([f"repos/{owner}/{repo}/license"]),
            provider=self.name,
            url=f"https://api.github.com/repos/{owner}/{repo}/license",
        )
        return (
            [_license_item(data, owner, repo)],
            f"https://github.com/{owner}/{repo}",
            "github_api",
        )

    def _op_tree(
        self, query: str, params: dict[str, Any]
    ) -> tuple[list[Item], str, str, list[ErrorItem]]:
        owner, repo = query.split("/", 1)
        branch = params.get("branch", "HEAD")
        recursive = bool(params.get("recursive", True))
        limit = int(params.get("limit", 200))
        args = [f"repos/{owner}/{repo}/git/trees/{branch}"]
        if recursive:
            args += ["-f", "recursive=1"]
        data = self._gh(args)
        entries = require_collection(
            data,
            provider=self.name,
            url=f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}",
            key="tree",
        )
        items = [_tree_item(e, owner, repo, branch) for e in entries[:limit]]
        warnings: list[ErrorItem] = []
        if data.get("truncated"):
            warnings.append(
                ErrorItem(
                    code="truncated",
                    message=f"tree for {owner}/{repo}@{branch} is truncated by GitHub",
                    provider=self.name,
                    operation="tree",
                    severity="warning",
                )
            )
        return (
            items,
            f"https://api.github.com/repos/{owner}/{repo}/git/trees/{branch}",
            "github_api",
            warnings,
        )

    def _op_starred(self, query: str, params: dict[str, Any]) -> tuple[list[Item], str, str]:
        limit = int(params.get("limit", 100))
        data = self._gh_list(f"users/{query}/starred", limit)
        return (
            [_repo_item(r) for r in data][:limit],
            f"https://api.github.com/users/{query}/starred",
            "github_api",
        )

    def _op_following(self, query: str, params: dict[str, Any]) -> tuple[list[Item], str, str]:
        limit = int(params.get("limit", 100))
        data = self._gh_list(f"users/{query}/following", limit)
        return (
            [_user_item(r) for r in data][:limit],
            f"https://api.github.com/users/{query}/following",
            "github_api",
        )

    def _op_followers(self, query: str, params: dict[str, Any]) -> tuple[list[Item], str, str]:
        limit = int(params.get("limit", 100))
        data = self._gh_list(f"users/{query}/followers", limit)
        return (
            [_user_item(r) for r in data][:limit],
            f"https://api.github.com/users/{query}/followers",
            "github_api",
        )

    def _op_repos(self, query: str, params: dict[str, Any]) -> tuple[list[Item], str, str]:
        limit = int(params.get("limit", 100))
        data = self._gh_list(f"users/{query}/repos", limit)
        return (
            [_repo_item(r) for r in data][:limit],
            f"https://api.github.com/users/{query}/repos",
            "github_api",
        )

    # -- transport -----------------------------------------------------------

    def _gh_list(self, endpoint: str, limit: int) -> list[dict[str, Any]]:
        limit = max(1, int(limit))
        if limit <= 100:
            data = self._gh([endpoint, "-f", f"per_page={limit}"])
        else:
            data = self._gh([endpoint, "-f", "per_page=100", "--paginate"])
        return require_object_list(
            data, provider=self.name, url=f"https://api.github.com/{endpoint}"
        )

    def _gh(self, args: list[str]) -> Any:
        gh = self._gh_path()
        timeout = self.config.providers.github.timeout_seconds
        call = [gh, "api", "--method", "GET", *args]
        try:
            if self._runner is not None:
                proc = self._runner(call, capture_output=True, text=True, timeout=timeout)
            else:
                proc = subprocess.run(call, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            raise ProviderHTTPError(
                "timeout",
                f"gh timed out after {timeout:.0f}s",
                retryable=True,
                provider="github",
                cause=str(exc),
            ) from exc
        except OSError as exc:
            raise ProviderHTTPError(
                "transport",
                f"failed to launch gh: {exc}",
                retryable=False,
                provider="github",
                cause=str(exc),
            ) from exc
        if proc.returncode != 0:
            raise self._classify(proc)
        if not (proc.stdout or "").strip():
            raise ProviderHTTPError(
                "parse", "gh returned empty output", retryable=False, provider="github"
            )
        try:
            return json.loads(proc.stdout)
        except json.JSONDecodeError as exc:
            raise ProviderHTTPError(
                "parse",
                "gh returned non-JSON output",
                retryable=False,
                provider="github",
                cause=str(exc),
            ) from exc

    def _gh_path(self) -> str:
        gh = self.config.providers.github.gh_path
        if self._runner is not None:
            return gh
        found = shutil.which(gh)
        if found:
            return found
        if os.path.sep in gh and Path(gh).exists():
            return gh
        raise ProviderHTTPError(
            "not_available",
            "GitHub CLI (gh) not found on PATH; install it and run 'gh auth login'",
            retryable=False,
            provider="github",
            preflight=True,
        )

    def _classify(self, proc: subprocess.CompletedProcess[str]) -> ProviderHTTPError:
        text = f"{proc.stderr or ''} {proc.stdout or ''}".lower()
        message = (proc.stderr or proc.stdout or f"gh exited {proc.returncode}").strip()
        if "429" in text or "rate limit" in text:
            return ProviderHTTPError("rate_limit", message, retryable=True, provider="github")
        if "404" in text or "not found" in text or "could not resolve" in text:
            return ProviderHTTPError("not_found", message, retryable=False, provider="github")
        if "401" in text or "unauthorized" in text or "authentication" in text:
            return ProviderHTTPError("auth", message, retryable=False, provider="github")
        if "403" in text:
            return ProviderHTTPError("auth", message, retryable=False, provider="github")
        if any(s in text for s in ("500", "502", "503")):
            return ProviderHTTPError("http", message, retryable=True, provider="github")
        return ProviderHTTPError("http", message, retryable=False, provider="github")
