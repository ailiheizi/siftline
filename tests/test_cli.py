from __future__ import annotations

import json

import pytest
from typer.testing import CliRunner

from siftline.cli import app
from siftline.models import ErrorItem, Item, Provenance, Result

runner = CliRunner()


@pytest.fixture
def config_file(tmp_path) -> str:
    path = tmp_path / "config.toml"
    path.write_text("[cache]\npath = 'var/cache.db'\nttl_seconds = 300\n")
    return str(path)


class _FakeProvider:
    def __init__(self, result: Result) -> None:
        self._result = result

    def run(self, operation, query, params, query_id) -> Result:
        result = self._result.model_copy(deep=True)
        result.query_id = query_id
        result.operation = operation
        result.query = query
        result.params = params
        result.retrieved_at = "2026-08-09T00:00:00Z"
        return result


def _ok_result() -> Result:
    return Result(
        query_id="fixed",
        provider="github",
        operation="search_repos",
        query="siftline",
        params={"limit": 3},
        items=[Item(url="https://github.com/owner/repo", title="owner/repo", source="owner/repo")],
        provenance=Provenance(transport="gh_cli", source="https://api.github.com"),
    )


def test_cli_json_contract(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("siftline.cli.get_provider", lambda *a, **k: _FakeProvider(_ok_result()))
    result = runner.invoke(
        app,
        [
            "--config",
            config_file,
            "--format",
            "json",
            "github",
            "search-repos",
            "siftline",
            "--limit",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    for key in (
        "schema_version",
        "query_id",
        "provider",
        "operation",
        "query",
        "retrieved_at",
        "items",
        "errors",
        "provenance",
    ):
        assert key in payload, key
    assert payload["schema_version"] == "1"
    assert payload["provider"] == "github"
    assert payload["operation"] == "search_repos"
    assert payload["items"][0]["url"] == "https://github.com/owner/repo"
    assert payload["provenance"]["cache"] == "miss"
    assert payload["params"] == {"limit": 3}


def test_cli_jsonl_one_envelope_per_line(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("siftline.cli.get_provider", lambda *a, **k: _FakeProvider(_ok_result()))
    result = runner.invoke(
        app, ["--config", config_file, "--format", "jsonl", "github", "search-repos", "siftline"]
    )
    assert result.exit_code == 0
    lines = [line for line in result.output.splitlines() if line.strip()]
    assert len(lines) == 1
    assert json.loads(lines[0])["schema_version"] == "1"


def test_cli_table_output(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("siftline.cli.get_provider", lambda *a, **k: _FakeProvider(_ok_result()))
    result = runner.invoke(
        app, ["--config", config_file, "--format", "table", "github", "search-repos", "siftline"]
    )
    assert result.exit_code == 0
    assert "github search_repos" in result.output
    assert "owner/repo" in result.output


def test_cli_exit_0_success(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("siftline.cli.get_provider", lambda *a, **k: _FakeProvider(_ok_result()))
    result = runner.invoke(app, ["--config", config_file, "github", "search-repos", "siftline"])
    assert result.exit_code == 0


def test_cli_exit_2_on_total_failure(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    bad = _ok_result()
    bad.items = []
    bad.errors = [ErrorItem(code="timeout", message="timed out", provider="github")]
    monkeypatch.setattr("siftline.cli.get_provider", lambda *a, **k: _FakeProvider(bad))
    result = runner.invoke(app, ["--config", config_file, "github", "search-repos", "siftline"])
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["items"] == []
    assert payload["errors"][0]["code"] == "timeout"


def test_cli_exit_3_on_partial(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    partial = _ok_result()
    partial.errors = [ErrorItem(code="transport", message="one provider failed", provider="exa")]
    monkeypatch.setattr("siftline.cli.get_provider", lambda *a, **k: _FakeProvider(partial))
    result = runner.invoke(app, ["--config", config_file, "github", "search-repos", "siftline"])
    assert result.exit_code == 3
    payload = json.loads(result.output)
    assert payload["items"]  # still has items
    assert payload["errors"]


def test_cli_usage_error_exit_2(config_file) -> None:
    result = runner.invoke(app, ["--config", config_file, "github", "search-repos"])
    assert result.exit_code == 2


def test_cli_bad_owner_repo_usage_error(config_file) -> None:
    result = runner.invoke(app, ["--config", config_file, "github", "repo", "norepo"])
    assert result.exit_code == 2
    assert "owner/repo" in result.output


def test_cli_query_id_reuse(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake(*a, **k):
        captured["provider"] = a[0]
        return _FakeProvider(_ok_result())

    monkeypatch.setattr("siftline.cli.get_provider", fake)
    result = runner.invoke(
        app, ["--config", config_file, "--query-id", "abc123", "hn", "search", "llm"]
    )
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["query_id"] == "abc123"


def test_cli_cache_subcommands(config_file) -> None:
    result = runner.invoke(app, ["--config", config_file, "--format", "json", "cache", "info"])
    assert result.exit_code == 0
    info = json.loads(result.output)
    assert "cache_entries" in info
    assert "log_entries" in info


def test_cli_cache_clear_requires_yes(config_file) -> None:
    result = runner.invoke(app, ["--config", config_file, "cache", "clear"], input="n\n")
    assert result.exit_code == 1  # typer.confirm aborts with code 1


def test_cli_cache_clear_with_yes(config_file) -> None:
    result = runner.invoke(
        app, ["--config", config_file, "--format", "json", "cache", "clear", "--yes"]
    )
    assert result.exit_code == 0
    removed = json.loads(result.output)
    assert "cache_removed" in removed


def test_cli_cache_log(config_file) -> None:
    result = runner.invoke(app, ["--config", config_file, "--format", "json", "cache", "log"])
    assert result.exit_code == 0
    assert isinstance(json.loads(result.output), list)


def test_cli_providers(config_file) -> None:
    result = runner.invoke(app, ["--config", config_file, "--format", "json", "providers"])
    assert result.exit_code == 0
    statuses = json.loads(result.output)
    names = {s["name"] for s in statuses}
    assert {"github", "hn", "exa", "tavily", "web"} <= names


def test_cli_doctor_no_network(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    report = {
        "checked_at": "2026-08-09T00:00:00Z",
        "checks": [{"check": "python", "status": "ok", "detail": "3.12", "hint": None}],
        "summary": {"ok": 1, "warn": 0, "error": 0, "unknown": 0},
        "providers": [],
    }
    monkeypatch.setattr("siftline.cli.run_checks", lambda *a, **k: report)
    result = runner.invoke(
        app, ["--config", config_file, "--format", "json", "doctor", "--no-network"]
    )
    assert result.exit_code == 0
    assert json.loads(result.output)["checks"][0]["check"] == "python"


def test_cli_version(config_file) -> None:
    result = runner.invoke(app, ["--config", config_file, "--version"])
    assert result.exit_code == 0
    assert "siftline" in result.output


def test_cli_ledger_command_registered() -> None:
    """Regression guard for the v4.21 ledger drift: the source CLI must always
    register the `ledger` command, so a stale installed binary is detectable by
    test failure instead of silently missing the command."""
    names = {cmd.name for cmd in app.registered_commands}
    assert "ledger" in names


def test_cli_version_equals_package_metadata() -> None:
    """pyproject.toml and src/siftline/__init__.py must stay in sync so
    `uv tool upgrade` can detect a version bump after source changes."""
    import tomllib
    from pathlib import Path

    from siftline import __version__

    repo = Path(__file__).resolve().parents[1]
    with open(repo / "pyproject.toml", "rb") as fh:
        pyproject = tomllib.load(fh)
    assert pyproject["project"]["version"] == __version__
