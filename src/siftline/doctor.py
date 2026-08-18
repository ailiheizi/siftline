from __future__ import annotations

import os
import shutil
import subprocess
import sys
from typing import Any

import httpx

from .config import Config
from .models import utc_now
from .storage import Storage
from .util import api_key


def _gh_message(config: Config) -> str:
    gh = config.providers.github.gh_path
    path = shutil.which(gh) or (gh if os.path.exists(gh) else None)
    if not path:
        return "gh CLI not found"
    try:
        proc = subprocess.run([path, "auth", "status"], capture_output=True, text=True, timeout=15)
        if proc.returncode == 0:
            return "gh CLI authenticated"
        text = (proc.stderr or proc.stdout or "").strip().splitlines()
        return text[-1][:200] if text else f"gh auth status failed (exit {proc.returncode})"
    except Exception as exc:  # noqa: BLE001
        return str(exc)


def gh_status(config: Config) -> dict[str, Any]:
    gh = config.providers.github.gh_path
    path = shutil.which(gh) or (gh if os.path.exists(gh) else None)
    if not path:
        return {"installed": False, "authed": False, "message": "gh CLI not found"}
    message = _gh_message(config)
    return {"installed": True, "authed": "authenticated" in message.lower(), "message": message}


def provider_statuses(config: Config) -> list[dict[str, Any]]:
    gh = gh_status(config)
    exa_key = api_key(config.providers.exa.api_key_env, ("EXA_API_KEY",))
    tavily_key = api_key(config.providers.tavily.api_key_env, ("TAVILY_API_KEY",))
    web_key = api_key(config.providers.openai_web.api_key_env, ("OPENAI_API_KEY",))
    model = config.providers.openai_web.model
    return [
        {
            "name": "github",
            "transport": "gh_cli",
            "requires_key": False,
            "key_present": True,
            "ok": gh["installed"] and gh["authed"],
            "detail": gh["message"],
        },
        {
            "name": "hn",
            "transport": "http",
            "requires_key": False,
            "key_present": True,
            "ok": True,
            "detail": "no key required (public Algolia API)",
        },
        {
            "name": "exa",
            "transport": "http",
            "requires_key": True,
            "key_present": bool(exa_key),
            "ok": bool(exa_key),
            "detail": f"configured via {config.providers.exa.api_key_env}"
            if exa_key
            else f"set {config.providers.exa.api_key_env} or EXA_API_KEY",
        },
        {
            "name": "tavily",
            "transport": "http",
            "requires_key": True,
            "key_present": bool(tavily_key),
            "ok": bool(tavily_key),
            "detail": f"configured via {config.providers.tavily.api_key_env}"
            if tavily_key
            else f"set {config.providers.tavily.api_key_env} or TAVILY_API_KEY",
        },
        {
            "name": "web",
            "transport": "http",
            "requires_key": True,
            "key_present": bool(web_key),
            "ok": bool(web_key) and bool(model),
            "detail": f"model={model}"
            if model
            else "no model configured (providers.openai_web.model)",
        },
    ]


def run_checks(config: Config, storage: Storage, network: bool = True) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    major, minor = sys.version_info[:2]
    checks.append(
        {
            "check": "python",
            "status": "ok" if (major, minor) >= (3, 11) else "warn",
            "detail": sys.version.split()[0],
            "hint": None,
        }
    )

    path = config.config_path
    checks.append(
        {
            "check": "config",
            "status": "ok" if path and path.exists() else "warn",
            "detail": str(path) if path else "defaults (no config file)",
            "hint": None
            if (path and path.exists())
            else "copy config.example.toml to a config path or set $SIFTLINE_CONFIG",
        }
    )

    try:
        stats = storage.stats()
        checks.append(
            {
                "check": "cache",
                "status": "ok",
                "detail": (
                    f"{stats['path']} ({stats['cache_entries']} entries, "
                    f"ttl {stats['ttl_seconds']}s)"
                ),
                "hint": None,
            }
        )
    except Exception as exc:  # noqa: BLE001
        checks.append({"check": "cache", "status": "error", "detail": str(exc), "hint": None})

    gh = gh_status(config)
    if not gh["installed"]:
        checks.append(
            {
                "check": "github_gh",
                "status": "warn",
                "detail": "gh CLI not found on PATH",
                "hint": "install GitHub CLI (e.g. brew install gh) and run 'gh auth login'",
            }
        )
    elif gh["authed"]:
        checks.append({"check": "github_gh", "status": "ok", "detail": gh["message"], "hint": None})
    else:
        checks.append(
            {
                "check": "github_gh",
                "status": "warn",
                "detail": gh["message"],
                "hint": "run 'gh auth login'",
            }
        )

    for name, primary, fallback in (
        ("exa", config.providers.exa.api_key_env, ("EXA_API_KEY",)),
        ("tavily", config.providers.tavily.api_key_env, ("TAVILY_API_KEY",)),
        ("openai_web", config.providers.openai_web.api_key_env, ("OPENAI_API_KEY",)),
    ):
        key = api_key(primary, fallback)
        checks.append(
            {
                "check": f"key_{name}",
                "status": "ok" if key else "error",
                "detail": "configured" if key else "missing",
                "hint": None if key else f"set {primary} (or {' or '.join(fallback)})",
            }
        )

    model = config.providers.openai_web.model
    checks.append(
        {
            "check": "openai_web_model",
            "status": "ok" if model else "error",
            "detail": model or "no model configured",
            "hint": None if model else "set providers.openai_web.model in config",
        }
    )

    if network:
        try:
            with httpx.Client(timeout=httpx.Timeout(5.0, connect=4.0)) as client:
                resp = client.get(
                    "https://hn.algolia.com/api/v1/search",
                    params={"query": "test", "hitsPerPage": 1},
                )
            checks.append(
                {
                    "check": "network_hn",
                    "status": "ok" if resp.status_code == 200 else "warn",
                    "detail": f"hn.algolia.com reachable (HTTP {resp.status_code})",
                    "hint": None,
                }
            )
        except Exception as exc:  # noqa: BLE001
            checks.append(
                {
                    "check": "network_hn",
                    "status": "unknown",
                    "detail": f"unreachable: {exc}",
                    "hint": None,
                }
            )

    summary = {"ok": 0, "warn": 0, "error": 0, "unknown": 0}
    for check in checks:
        summary[check["status"]] += 1

    return {
        "checked_at": utc_now(),
        "checks": checks,
        "summary": summary,
        "providers": provider_statuses(config),
    }
