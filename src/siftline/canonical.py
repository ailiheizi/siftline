from __future__ import annotations

import re
from collections.abc import Iterable
from urllib.parse import urlsplit, urlunsplit

from .models import Item

_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")
_SCP_RE = re.compile(r"^git@github\.com[:/](?P<path>.+)$")
_SSH_RE = re.compile(r"^ssh://git@github\.com/(?P<path>.+)$")
_GITHUB_HTTPS_RE = re.compile(r"^(?P<scheme>git\+https|https)://github\.com/(?P<path>.+)$")


def _clean_path(path: str) -> str:
    path = path.rstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    return path


def github_repo_url(raw: str) -> str | None:
    """Normalize any GitHub repo reference (scp, ssh, git+https, https) to https://github.com/<owner>/<repo>."""
    raw = (raw or "").strip()
    m = _SCP_RE.match(raw) or _SSH_RE.match(raw) or _GITHUB_HTTPS_RE.match(raw)
    if not m:
        return None
    path = _clean_path(m.group("path"))
    parts = path.split("/")
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    return f"https://github.com/{parts[0]}/{parts[1]}"


def canonical_url(raw: str) -> str:
    """Canonicalize an http(s) URL: lowercase scheme/host, drop default ports and trailing slashes.

    Non-http(s) values are returned unchanged so identity-based identifiers keep
    their original shape for dedup purposes.
    """
    raw = (raw or "").strip()
    if not raw or not _SCHEME_RE.match(raw):
        return raw
    try:
        parts = urlsplit(raw)
    except ValueError:
        return raw
    scheme = parts.scheme.lower()
    if scheme not in ("http", "https"):
        return raw
    host = (parts.hostname or "").lower()
    port = parts.port
    netloc = host
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        netloc = f"{host}:{port}"
    path = parts.path.rstrip("/") or "/"
    return urlunsplit((scheme, netloc, path, parts.query, parts.fragment))


def dedup_key(url: str) -> str:
    """Case-insensitive dedup identity for a URL. Fragments are ignored."""
    return canonical_url(url).split("#", 1)[0].lower()


def normalize_items(items: Iterable[Item]) -> list[Item]:
    out: list[Item] = []
    for item in items:
        if item.url:
            item.url = canonical_url(item.url)
        out.append(item)
    return out
