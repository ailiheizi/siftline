from __future__ import annotations

import contextlib
import json
import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Any, cast

import typer
from rich.console import Console
from rich.table import Table

from . import __version__
from .config import Config
from .doctor import provider_statuses, run_checks
from .models import ErrorItem, Provenance, Result, utc_now
from .providers import get_provider
from .storage import Storage

console = Console()

app = typer.Typer(
    name="siftline",
    add_completion=False,
    context_settings={"help_option_names": ["-h", "--help"]},
)


class OutputFormat(str, Enum):  # noqa: UP042 -- typer requires a str-Enum for choices
    json = "json"
    jsonl = "jsonl"
    table = "table"


@dataclass
class Runtime:
    config: Config
    storage: Storage
    format: OutputFormat
    query_id: str | None = None


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    config: str | None = typer.Option(
        None,
        "--config",
        help="Path to a config TOML. Defaults to $SIFTLINE_CONFIG or the platform config dir.",
    ),
    format: OutputFormat = typer.Option(
        OutputFormat.json, "--format", "-f", help="Output format for machine-facing commands."
    ),
    cache: bool = typer.Option(
        True, "--cache/--no-cache", help="Enable or disable the SQLite response cache."
    ),
    ttl: int | None = typer.Option(
        None, "--ttl", help="Override cache TTL in seconds for this run."
    ),
    query_id: str | None = typer.Option(
        None, "--query-id", help="Stable id recorded in the output envelope and query log."
    ),
    version: bool = typer.Option(False, "--version", help="Print version and exit."),
) -> None:
    if version:
        typer.echo(f"siftline {__version__}")
        raise typer.Exit()
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())
        raise typer.Exit()
    cfg = Config.load(config)
    storage = Storage(
        path=cfg.cache_path,
        ttl_seconds=ttl if ttl is not None else cfg.cache.ttl_seconds,
        enabled=cache and cfg.cache.enabled,
    )
    ctx.obj = Runtime(config=cfg, storage=storage, format=format, query_id=query_id)


def _rt(ctx: typer.Context) -> Runtime:
    return cast("Runtime", ctx.obj)


def _safe_record(rt: Runtime, entry: dict[str, Any]) -> None:
    """Write a machine-ledger row without ever crashing the sensor.

    Ledger writes must not mask the original result or raise during an
    exceptional path; a storage failure degrades to an unrecorded event.
    """
    with contextlib.suppress(Exception):  # noqa: BLE001 -- a sensor must never crash
        rt.storage.log_append(entry)


def _record_validation(
    rt: Runtime, provider_name: str, operation: str, query: str, params: dict[str, Any]
) -> None:
    """Record an explicit preflight validation failure (no provider call)."""
    _safe_record(
        rt,
        {
            "ts": utc_now(),
            "query_id": rt.query_id or uuid.uuid4().hex,
            "provider": provider_name,
            "operation": operation,
            "query": query,
            "params": params,
            "cache": "miss",
            "ttl": rt.storage.ttl_seconds,
            "elapsed_ms": 0,
            "item_count": 0,
            "error_count": 1,
            "outcome": "validation_failed",
            "provider_called": False,
            "error_codes": ["usage"],
        },
    )


def _run(
    ctx: typer.Context, provider_name: str, operation: str, query: str, params: dict[str, Any]
) -> None:
    rt = _rt(ctx)
    query_id = rt.query_id or uuid.uuid4().hex
    provider = None
    try:
        provider = get_provider(provider_name, rt.config, rt.storage)
        result = provider.run(operation, query, params, query_id)
    except Exception as exc:  # noqa: BLE001 -- a sensor must never crash
        result = Result(
            query_id=query_id,
            provider=provider_name,
            operation=operation,
            query=query,
            params=params,
            provenance=Provenance(transport="unknown"),
            errors=[
                ErrorItem(
                    code="internal", message=str(exc), provider=provider_name, operation=operation
                )
            ],
        )
        _safe_record(
            rt,
            {
                "ts": utc_now(),
                "query_id": query_id,
                "provider": provider_name,
                "operation": operation,
                "query": query,
                "params": params,
                "cache": "miss",
                "ttl": rt.storage.ttl_seconds,
                "elapsed_ms": 0,
                "item_count": 0,
                "error_count": 1,
                "outcome": "internal_failed",
                # provider_called is false only when provider construction itself
                # failed before a provider existed. When an unexpected exception
                # escaped an existing provider's run(), the CLI cannot know
                # whether an external call occurred, so the call state stays null
                # (an unknown provider-call state), never a fabricated false.
                "provider_called": False if provider is None else None,
                "error_codes": ["internal"],
            },
        )
    emit_result(rt.format, result)
    raise typer.Exit(code=exit_code(result))


def exit_code(result: Result) -> int:
    hard = [e for e in result.errors if e.severity == "error"]
    if not hard:
        return 0
    return 3 if result.items else 2


def emit_result(format: OutputFormat, result: Result) -> None:
    if format == OutputFormat.table:
        _table_result(result)
    elif format == OutputFormat.jsonl:
        print(result.model_dump_json())
    else:
        print(result.model_dump_json(indent=2))


def _table_result(result: Result) -> None:
    if result.items:
        table = Table(title=f"{result.provider} {result.operation}")
        table.add_column("url", style="cyan", no_wrap=False)
        table.add_column("title", max_width=60)
        table.add_column("source", max_width=40)
        for item in result.items:
            table.add_row(item.url or "", item.title or "", item.source or "")
        console.print(table)
    for error in result.errors:
        color = "yellow" if error.severity == "warning" else "red"
        console.print(f"[{color}]{error.provider} {error.code}: {error.message}[/]")


def _emit_rows(rows: list[dict[str, Any]], format: OutputFormat, columns: list[str]) -> None:
    if format == OutputFormat.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
    elif format == OutputFormat.jsonl:
        for row in rows:
            print(json.dumps(row, ensure_ascii=False))
    else:
        table = Table()
        for column in columns:
            table.add_column(column, no_wrap=False)
        for row in rows:
            table.add_row(*(str(row.get(c, "")) for c in columns))
        console.print(table)


def _emit_mapping(
    mapping: dict[str, Any], format: OutputFormat, columns: list[str], title: str | None = None
) -> None:
    if format == OutputFormat.json:
        print(json.dumps(mapping, indent=2, ensure_ascii=False))
    elif format == OutputFormat.jsonl:
        print(json.dumps(mapping, ensure_ascii=False))
    else:
        table = Table(title=title)
        for column in columns:
            table.add_column(column, no_wrap=False)
        table.add_row(*(str(mapping.get(c, "")) for c in columns))
        console.print(table)


# -- diagnostics -------------------------------------------------------------


@app.command("doctor")
def doctor_cmd(
    ctx: typer.Context,
    no_network: bool = typer.Option(False, "--no-network", help="Skip live reachability checks."),
) -> None:
    rt = _rt(ctx)
    report = run_checks(rt.config, rt.storage, network=not no_network)
    if rt.format == OutputFormat.table:
        table = Table(title="siftline doctor")
        table.add_column("check")
        table.add_column("status")
        table.add_column("detail")
        table.add_column("hint")
        for check in report["checks"]:
            table.add_row(
                check["check"],
                check["status"],
                str(check["detail"] or ""),
                str(check["hint"] or ""),
            )
        console.print(table)
    elif rt.format == OutputFormat.jsonl:
        for check in report["checks"]:
            print(json.dumps(check, ensure_ascii=False))
    else:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    raise typer.Exit(0)


@app.command("providers")
def providers_cmd(ctx: typer.Context) -> None:
    rt = _rt(ctx)
    statuses = provider_statuses(rt.config)
    _emit_rows(
        statuses, rt.format, ["name", "transport", "requires_key", "key_present", "ok", "detail"]
    )
    raise typer.Exit(0)


# -- machine research ledger -------------------------------------------------

LEDGER_ENTRY_COLUMNS = [
    "ts",
    "query_id",
    "provider",
    "operation",
    "query",
    "cache",
    "outcome",
    "provider_called",
    "elapsed_ms",
    "item_count",
    "error_count",
    "error_codes",
]


@app.command("ledger")
def ledger_cmd(
    ctx: typer.Context,
    query_id: str | None = typer.Option(
        None, "--query-id", help="Filter the machine ledger by a stable research-run query id."
    ),
    limit: int = typer.Option(50, "--limit", min=1, max=10000),
) -> None:
    """Inspect the machine research ledger: a stable summary plus raw entries."""
    rt = _rt(ctx)
    data = rt.storage.ledger(query_id=query_id, limit=limit)
    if rt.format == OutputFormat.json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    elif rt.format == OutputFormat.jsonl:
        print(json.dumps(data["summary"], ensure_ascii=False))
        for entry in data["entries"]:
            print(json.dumps(entry, ensure_ascii=False))
    else:
        table = Table(title="siftline ledger")
        for column in LEDGER_ENTRY_COLUMNS:
            table.add_column(column, no_wrap=False)
        for entry in data["entries"]:
            table.add_row(*(str(entry.get(c, "")) for c in LEDGER_ENTRY_COLUMNS))
        console.print(table)
    raise typer.Exit(0)


# -- cache -------------------------------------------------------------------


cache_app = typer.Typer(help="Inspect or clear the SQLite cache and the machine research ledger.")
app.add_typer(cache_app, name="cache")


@cache_app.command("info")
def cache_info(ctx: typer.Context) -> None:
    rt = _rt(ctx)
    _emit_mapping(
        rt.storage.stats(),
        rt.format,
        ["path", "size_bytes", "cache_entries", "log_entries", "ttl_seconds", "enabled"],
    )
    raise typer.Exit(0)


@cache_app.command("clear")
def cache_clear(
    ctx: typer.Context, yes: bool = typer.Option(False, "--yes", "-y", help="Do not prompt.")
) -> None:
    rt = _rt(ctx)
    stats = rt.storage.stats()
    if not yes:
        message = (
            f"Delete {stats['cache_entries']} cache entries and {stats['log_entries']} log entries?"
        )
        typer.confirm(message, abort=True)
    removed = rt.storage.clear()
    _emit_mapping(removed, rt.format, ["cache_removed", "log_removed"])
    raise typer.Exit(0)


@cache_app.command("log")
def cache_log(ctx: typer.Context, limit: int = typer.Option(50, min=1, max=10000)) -> None:
    rt = _rt(ctx)
    _emit_rows(
        rt.storage.log_entries(limit),
        rt.format,
        [
            "ts",
            "query_id",
            "provider",
            "operation",
            "query",
            "cache",
            "outcome",
            "provider_called",
            "elapsed_ms",
            "item_count",
            "error_count",
            "error_codes",
        ],
    )
    raise typer.Exit(0)


# -- GitHub ------------------------------------------------------------------


github_app = typer.Typer(
    help="GitHub provider. Read-only queries through the authenticated gh CLI (gh api)."
)
app.add_typer(github_app, name="github")


def _require_owner_repo(value: str) -> str:
    if "/" not in value or len(value.split("/")) != 2 or not all(value.split("/")):
        raise typer.BadParameter("expected owner/repo (for example claude-ai/claude-code)")
    return value


def _validated_owner_repo_run(
    ctx: typer.Context, operation: str, value: str, params: dict[str, Any]
) -> None:
    """Run a GitHub operation after explicit owner/repo validation.

    A failed validation is recorded in the machine ledger as
    ``validation_failed`` with ``provider_called=false`` — the request never
    reached a provider or external transport, so it must not count as a call.
    """
    rt = _rt(ctx)
    try:
        _require_owner_repo(value)
    except typer.BadParameter:
        _record_validation(rt, "github", operation, value, params)
        raise
    _run(ctx, "github", operation, value, params)


@github_app.command("search-repos")
def github_search_repos(
    ctx: typer.Context,
    query: str = typer.Argument(help="GitHub repository search query (GitHub search syntax)."),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    _run(ctx, "github", "search_repos", query, {"limit": limit})


@github_app.command("search-code")
def github_search_code(
    ctx: typer.Context,
    query: str = typer.Argument(help="GitHub code search query (GitHub search syntax)."),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    _run(ctx, "github", "search_code", query, {"limit": limit})


@github_app.command("repo")
def github_repo(
    ctx: typer.Context,
    owner_repo: str = typer.Argument(help="owner/repo to inspect."),
) -> None:
    _validated_owner_repo_run(ctx, "repo", owner_repo, {})


@github_app.command("readme")
def github_readme(
    ctx: typer.Context,
    owner_repo: str = typer.Argument(help="owner/repo whose README to fetch."),
) -> None:
    _validated_owner_repo_run(ctx, "readme", owner_repo, {})


@github_app.command("license")
def github_license(
    ctx: typer.Context,
    owner_repo: str = typer.Argument(help="owner/repo whose LICENSE file to fetch."),
) -> None:
    _validated_owner_repo_run(ctx, "license", owner_repo, {})


@github_app.command("tree")
def github_tree(
    ctx: typer.Context,
    owner_repo: str = typer.Argument(help="owner/repo whose file tree to fetch."),
    branch: str = typer.Option("HEAD", help="Branch or ref to list."),
    recursive: bool = typer.Option(
        True, "--recursive/--no-recursive", help="Recursively list the tree."
    ),
    limit: int = typer.Option(200, min=1, max=10000),
) -> None:
    _validated_owner_repo_run(
        ctx,
        "tree",
        owner_repo,
        {"branch": branch, "recursive": recursive, "limit": limit},
    )


@github_app.command("starred")
def github_starred(
    ctx: typer.Context,
    owner: str = typer.Argument(help="User whose starred repositories to list."),
    limit: int = typer.Option(100, min=1, max=1000),
) -> None:
    _run(ctx, "github", "starred", owner, {"limit": limit})


@github_app.command("following")
def github_following(
    ctx: typer.Context,
    owner: str = typer.Argument(help="User whose following list to fetch."),
    limit: int = typer.Option(100, min=1, max=1000),
) -> None:
    _run(ctx, "github", "following", owner, {"limit": limit})


@github_app.command("followers")
def github_followers(
    ctx: typer.Context,
    owner: str = typer.Argument(help="User whose followers to list."),
    limit: int = typer.Option(100, min=1, max=1000),
) -> None:
    _run(ctx, "github", "followers", owner, {"limit": limit})


@github_app.command("repos")
def github_repos(
    ctx: typer.Context,
    owner: str = typer.Argument(help="User whose repositories to list."),
    limit: int = typer.Option(100, min=1, max=1000),
) -> None:
    _run(ctx, "github", "repos", owner, {"limit": limit})


# -- Hacker News -------------------------------------------------------------


hn_app = typer.Typer(help="Hacker News provider via the public Algolia API (no key required).")
app.add_typer(hn_app, name="hn")


@hn_app.command("search")
def hn_search(
    ctx: typer.Context,
    query: str = typer.Argument(help="Search query for Hacker News items."),
    tags: str | None = typer.Option(
        None, "--tags", help="Algolia tags filter, e.g. story,comment."
    ),
    limit: int = typer.Option(10, min=1, max=100),
) -> None:
    params: dict[str, Any] = {"limit": limit}
    if tags:
        params["tags"] = tags
    _run(ctx, "hn", "search", query, params)


@hn_app.command("item")
def hn_item(
    ctx: typer.Context,
    item_id: int = typer.Argument(help="Hacker News item/story id."),
) -> None:
    _run(ctx, "hn", "item", str(item_id), {"id": item_id})


# -- Exa ---------------------------------------------------------------------


exa_app = typer.Typer(help="Exa provider (requires SIFTLINE_EXA_API_KEY or EXA_API_KEY).")
app.add_typer(exa_app, name="exa")


@exa_app.command("search")
def exa_search(
    ctx: typer.Context,
    query: str = typer.Argument(help="Search query."),
    limit: int = typer.Option(10, min=1, max=50),
) -> None:
    _run(ctx, "exa", "search", query, {"limit": limit})


# -- Tavily ------------------------------------------------------------------


tavily_app = typer.Typer(
    help="Tavily provider (requires SIFTLINE_TAVILY_API_KEY or TAVILY_API_KEY)."
)
app.add_typer(tavily_app, name="tavily")


@tavily_app.command("search")
def tavily_search(
    ctx: typer.Context,
    query: str = typer.Argument(help="Search query."),
    limit: int = typer.Option(10, min=1, max=50),
) -> None:
    _run(ctx, "tavily", "search", query, {"limit": limit})


# -- OpenAI-compatible web_search --------------------------------------------


web_app = typer.Typer(
    help=(
        "OpenAI-compatible Responses web_search "
        "(requires SIFTLINE_OPENAI_API_KEY or OPENAI_API_KEY)."
    )
)
app.add_typer(web_app, name="web")


@web_app.command("search")
def web_search(
    ctx: typer.Context,
    query: str = typer.Argument(help="Search query."),
    limit: int | None = typer.Option(
        None, help="Recorded in params for reproducibility; the API decides result count."
    ),
) -> None:
    params: dict[str, Any] = {}
    if limit is not None:
        params["limit"] = limit
    _run(ctx, "web", "search", query, params)
