from __future__ import annotations

import json
import sqlite3

import httpx
import pytest
from typer.testing import CliRunner

from siftline.cli import app
from siftline.providers.exa import ExaProvider
from siftline.providers.github import GithubProvider
from siftline.providers.hn import HNProvider
from siftline.storage import Storage

runner = CliRunner()

_OLD_SCHEMA = """
CREATE TABLE cache (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    retrieved_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE query_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    query_id TEXT NOT NULL,
    provider TEXT NOT NULL,
    operation TEXT NOT NULL,
    query TEXT NOT NULL,
    params TEXT NOT NULL,
    cache TEXT NOT NULL,
    ttl INTEGER NOT NULL,
    elapsed_ms INTEGER NOT NULL,
    item_count INTEGER NOT NULL,
    error_count INTEGER NOT NULL
);
"""


def _hn_payload() -> dict:
    return {
        "hits": [{"objectID": "1", "title": "T", "url": "https://e.example/1"}],
        "nbHits": 1,
    }


def _hn_provider(config, storage) -> HNProvider:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_hn_payload())

    return HNProvider(config, storage, http_transport=httpx.MockTransport(handler))


def _entries(store: Storage) -> list[dict]:
    return store.ledger(limit=100)["entries"]


# -- outcomes -----------------------------------------------------------------


def test_provider_succeeded_records_true_call(config, storage) -> None:
    prov = _hn_provider(config, storage)
    result = prov.run("search", "my tool", {"limit": 10}, "q1")
    assert result.provenance.cache == "miss"
    assert not result.has_hard_errors()
    entry = _entries(storage)[0]
    assert entry["outcome"] == "provider_succeeded"
    assert entry["provider_called"] is True
    assert entry["cache"] == "miss"
    assert entry["error_codes"] == []
    assert entry["query"] == "my tool"
    assert entry["item_count"] == 1


def test_cache_hit_records_no_provider_call(config, storage) -> None:
    prov = _hn_provider(config, storage)
    prov.run("search", "my tool", {"limit": 10}, "q1")
    second = prov.run("search", "my tool", {"limit": 10}, "q1")
    assert second.provenance.cache == "hit"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "cache_hit"
    assert entry["provider_called"] is False
    assert entry["cache"] == "hit"
    assert entry["item_count"] == 1


def test_cache_hit_under_new_query_id_carries_current_id(config, storage) -> None:
    prov = _hn_provider(config, storage)
    first = prov.run("search", "my tool", {"limit": 10}, "old-id")
    assert first.query_id == "old-id"
    second = prov.run("search", "my tool", {"limit": 10}, "new-id")
    assert second.provenance.cache == "hit"
    assert second.query_id == "new-id"
    entries = storage.ledger(query_id="new-id", limit=100)["entries"]
    assert len(entries) == 1
    assert entries[0]["query_id"] == "new-id"
    assert entries[0]["outcome"] == "cache_hit"
    assert entries[0]["provider_called"] is False


def test_missing_key_is_validation_failure_not_provider_call(config, storage) -> None:
    prov = ExaProvider(
        config, storage, http_transport=httpx.MockTransport(lambda r: httpx.Response(200, json={}))
    )
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "auth"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "validation_failed"
    assert entry["provider_called"] is False
    assert entry["error_codes"] == ["auth"]


def test_unsupported_operation_is_validation_failure(config, storage) -> None:
    prov = _hn_provider(config, storage)
    result = prov.run("not_a_thing", "x", {}, "q1")
    assert result.errors[0].code == "usage"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "validation_failed"
    assert entry["provider_called"] is False
    assert entry["error_codes"] == ["usage"]


def test_unavailable_gh_is_validation_failure(
    config, storage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("siftline.providers.github.shutil.which", lambda _: None)
    prov = GithubProvider(config, storage)
    result = prov.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "not_available"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "validation_failed"
    assert entry["provider_called"] is False
    assert entry["error_codes"] == ["not_available"]


def test_remote_http_error_is_provider_failure(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(429, json={})

    prov = HNProvider(config, storage, http_transport=httpx.MockTransport(handler))
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "rate_limit"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "provider_failed"
    assert entry["provider_called"] is True
    assert entry["error_codes"] == ["rate_limit"]


def test_remote_gh_auth_error_is_provider_failure(config, storage) -> None:
    def runner(args: list[str], **kwargs):
        import subprocess

        return subprocess.CompletedProcess(
            args, 1, stdout="", stderr="gh: HTTP 401: Bad credentials"
        )

    prov = GithubProvider(config, storage, runner=runner)
    result = prov.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "auth"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "provider_failed"
    assert entry["provider_called"] is True
    assert entry["error_codes"] == ["auth"]


def test_parse_failure_after_transport_is_postprocess(config, storage) -> None:
    def runner(args: list[str], **kwargs):
        import subprocess

        return subprocess.CompletedProcess(args, 0, stdout="this is not json", stderr="")

    prov = GithubProvider(config, storage, runner=runner)
    result = prov.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.errors[0].code == "parse"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "postprocess_failed"
    assert entry["provider_called"] is True
    assert entry["error_codes"] == ["parse"]


def test_timeout_is_provider_failure(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("no route", request=request)

    prov = HNProvider(config, storage, http_transport=httpx.MockTransport(handler))
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "timeout"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "provider_failed"
    assert entry["provider_called"] is True


def test_non_object_payload_is_postprocess_failure(config, storage) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>proxy error page</html>")

    prov = HNProvider(config, storage, http_transport=httpx.MockTransport(handler))
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "parse"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "postprocess_failed"
    assert entry["provider_called"] is True
    assert entry["error_codes"] == ["parse"]


def test_invalid_collection_shape_is_postprocess_failure(config, storage) -> None:
    """A JSON object with a malformed collection is parse, not an internal failure."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"hits": "not-a-list"})

    prov = HNProvider(config, storage, http_transport=httpx.MockTransport(handler))
    result = prov.run("search", "x", {"limit": 3}, "q1")
    assert result.errors[0].code == "parse"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "postprocess_failed"
    assert entry["provider_called"] is True
    assert entry["error_codes"] == ["parse"]


def test_hard_error_returned_by_provider_is_postprocess(config, storage) -> None:
    """A returned result with a hard downstream error (github empty_result) is
    postprocess_failed with provider_called true, never provider_succeeded."""

    def runner(args: list[str], **kwargs):
        import subprocess

        return subprocess.CompletedProcess(
            args, 0, stdout=json.dumps({"total_count": 5, "items": []}), stderr=""
        )

    prov = GithubProvider(config, storage, runner=runner)
    result = prov.run("search_repos", "x", {"limit": 5}, "q1")
    assert result.has_hard_errors()
    assert result.errors[0].code == "empty_result"
    entry = _entries(storage)[0]
    assert entry["outcome"] == "postprocess_failed"
    assert entry["provider_called"] is True
    assert entry["error_codes"] == ["empty_result"]


def test_warning_only_result_is_provider_success(config, storage) -> None:
    """Warnings-only results (e.g. a truncated tree) remain provider_succeeded."""

    def runner(args: list[str], **kwargs):
        import subprocess

        return subprocess.CompletedProcess(
            args,
            0,
            stdout=json.dumps(
                {
                    "sha": "s",
                    "truncated": True,
                    "tree": [{"path": "a", "type": "blob", "mode": "100644", "sha": "x"}],
                }
            ),
            stderr="",
        )

    prov = GithubProvider(config, storage, runner=runner)
    result = prov.run("tree", "o/r", {"branch": "main", "recursive": True, "limit": 200}, "q1")
    assert not result.has_hard_errors()
    assert any(e.severity == "warning" for e in result.errors)
    entry = _entries(storage)[0]
    assert entry["outcome"] == "provider_succeeded"
    assert entry["provider_called"] is True


# -- summary ------------------------------------------------------------------


def test_summary_counts_and_provider_calls(config, storage) -> None:
    prov = _hn_provider(config, storage)
    prov.run("search", "a", {"limit": 10}, "run")
    prov.run("search", "a", {"limit": 10}, "run")  # cache hit
    prov.run("nope", "x", {}, "run")  # validation failure

    summary = storage.ledger(query_id="run")["summary"]
    assert summary["attempts"] == 3
    assert summary["provider_calls"] == 1
    assert summary["unknown_provider_call_states"] == 0
    assert summary["provider_successes"] == 1
    assert summary["cache_hits"] == 1
    assert summary["validation_failures"] == 1
    assert summary["postprocess_failures"] == 0
    assert summary["provider_failures"] == 0
    assert summary["internal_failures"] == 0
    assert summary["unclassified"] == 0
    assert summary["attempts"] == sum(
        summary[k]
        for k in (
            "cache_hits",
            "validation_failures",
            "provider_successes",
            "postprocess_failures",
            "provider_failures",
            "internal_failures",
            "unclassified",
        )
    )


def test_summary_filtering_by_query_id(config, storage) -> None:
    prov = _hn_provider(config, storage)
    prov.run("search", "a", {"limit": 10}, "run-A")
    prov.run("search", "b", {"limit": 10}, "run-B")
    only_a = storage.ledger(query_id="run-A")["summary"]
    assert only_a["attempts"] == 1
    assert only_a["provider_successes"] == 1
    assert storage.ledger(limit=100)["summary"]["attempts"] == 2


# -- CLI contract -------------------------------------------------------------


@pytest.fixture
def config_file(tmp_path) -> str:
    path = tmp_path / "config.toml"
    path.write_text("[cache]\npath = 'var/cache.db'\nttl_seconds = 300\n")
    return str(path)


def _install_fake_hn_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_hn_payload())

    def fake_get_provider(name, config, storage, **kwargs):
        return HNProvider(config, storage, http_transport=httpx.MockTransport(handler))

    monkeypatch.setattr("siftline.cli.get_provider", fake_get_provider)


def test_cli_ledger_query_id_filtering(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_hn_provider(monkeypatch)
    for query_id, query in [("run-A", "x"), ("run-A", "x"), ("run-B", "y")]:
        result = runner.invoke(
            app, ["--config", config_file, "--query-id", query_id, "hn", "search", query]
        )
        assert result.exit_code == 0, result.output

    out = runner.invoke(
        app,
        [
            "--config",
            config_file,
            "--format",
            "json",
            "ledger",
            "--query-id",
            "run-A",
            "--limit",
            "50",
        ],
    )
    assert out.exit_code == 0, out.output
    payload = json.loads(out.output)
    assert payload["summary"]["attempts"] == 2
    assert payload["summary"]["cache_hits"] == 1
    assert payload["summary"]["provider_successes"] == 1
    assert payload["summary"]["provider_calls"] == 1
    assert all(entry["query_id"] == "run-A" for entry in payload["entries"])

    all_out = runner.invoke(
        app, ["--config", config_file, "--format", "json", "ledger", "--limit", "50"]
    )
    assert json.loads(all_out.output)["summary"]["attempts"] == 3


def test_cli_ledger_jsonl_shape(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_hn_provider(monkeypatch)
    runner.invoke(app, ["--config", config_file, "--query-id", "r", "hn", "search", "x"])
    out = runner.invoke(
        app, ["--config", config_file, "--format", "jsonl", "ledger", "--query-id", "r"]
    )
    assert out.exit_code == 0, out.output
    lines = [json.loads(line) for line in out.output.splitlines() if line.strip()]
    summary_keys = {
        "attempts",
        "provider_calls",
        "unknown_provider_call_states",
        "cache_hits",
        "validation_failures",
        "provider_successes",
        "postprocess_failures",
        "provider_failures",
        "internal_failures",
        "unclassified",
    }
    assert set(lines[0].keys()) == summary_keys
    assert len(lines) == 2  # summary + one entry


def test_cli_cache_log_exposes_ledger_fields(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_fake_hn_provider(monkeypatch)
    runner.invoke(app, ["--config", config_file, "--query-id", "r", "hn", "search", "x"])
    out = runner.invoke(app, ["--config", config_file, "--format", "json", "cache", "log"])
    assert out.exit_code == 0, out.output
    entries = json.loads(out.output)
    assert isinstance(entries, list) and entries
    assert {"outcome", "provider_called", "error_codes"} <= set(entries[0].keys())
    assert entries[0]["outcome"] == "provider_succeeded"
    assert entries[0]["provider_called"] is True


def test_cli_owner_repo_validation_logged_without_github(
    config_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a, **k):
        raise AssertionError("provider must not be constructed for a validation failure")

    monkeypatch.setattr("siftline.cli.get_provider", boom)
    result = runner.invoke(app, ["--config", config_file, "github", "repo", "norepo"])
    assert result.exit_code == 2
    out = runner.invoke(
        app, ["--config", config_file, "--format", "json", "ledger", "--limit", "10"]
    )
    payload = json.loads(out.output)
    assert payload["summary"]["validation_failures"] == 1
    entry = payload["entries"][0]
    assert entry["provider"] == "github"
    assert entry["operation"] == "repo"
    assert entry["query"] == "norepo"
    assert entry["outcome"] == "validation_failed"
    assert entry["provider_called"] is False
    assert entry["error_codes"] == ["usage"]


def test_cli_internal_failure_logged(config_file, monkeypatch: pytest.MonkeyPatch) -> None:
    class _BoomProvider:
        def run(self, *a, **k):
            raise RuntimeError("unexpected boom")

    monkeypatch.setattr("siftline.cli.get_provider", lambda *a, **k: _BoomProvider())
    result = runner.invoke(app, ["--config", config_file, "hn", "search", "x"])
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["errors"][0]["code"] == "internal"

    out = runner.invoke(
        app, ["--config", config_file, "--format", "json", "ledger", "--limit", "10"]
    )
    payload = json.loads(out.output)
    assert payload["summary"]["internal_failures"] == 1
    assert payload["summary"]["unknown_provider_call_states"] == 1
    entry = payload["entries"][0]
    assert entry["outcome"] == "internal_failed"
    # An unexpected exception escaped an existing provider's run(): the CLI
    # cannot know whether an external call occurred, so the call state stays null
    # (an unknown provider-call state), never a fabricated false.
    assert entry["provider_called"] is None
    assert entry["error_codes"] == ["internal"]
    assert entry["legacy"] is False


def test_cli_provider_construction_failure_logged(
    config_file, monkeypatch: pytest.MonkeyPatch
) -> None:
    def boom(*a, **k):
        raise RuntimeError("construction boom")

    monkeypatch.setattr("siftline.cli.get_provider", boom)
    result = runner.invoke(app, ["--config", config_file, "hn", "search", "x"])
    assert result.exit_code == 2
    payload = json.loads(result.output)
    assert payload["errors"][0]["code"] == "internal"

    out = runner.invoke(
        app, ["--config", config_file, "--format", "json", "ledger", "--limit", "10"]
    )
    payload = json.loads(out.output)
    assert payload["summary"]["internal_failures"] == 1
    entry = payload["entries"][0]
    assert entry["outcome"] == "internal_failed"
    # Construction itself failed before a provider existed: no truthful
    # dispatched-request event can be formed, so the call state is false.
    assert entry["provider_called"] is False
    assert entry["error_codes"] == ["internal"]
    assert entry["legacy"] is False


# -- migration ----------------------------------------------------------------


def _write_legacy_db(path, rows) -> None:
    conn = sqlite3.connect(str(path))
    conn.executescript(_OLD_SCHEMA)
    for row in rows:
        conn.execute(
            "INSERT INTO query_log (ts, query_id, provider, operation, query, params, cache,"
            " ttl, elapsed_ms, item_count, error_count) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            row,
        )
    conn.commit()
    conn.close()


def test_migration_adds_columns_and_marks_legacy_ambiguity(tmp_path) -> None:
    path = tmp_path / "legacy.db"
    _write_legacy_db(
        path,
        [
            (
                "2026-08-01T00:00:00Z",
                "legacy-run",
                "github",
                "repo",
                "a/b",
                "{}",
                "miss",
                3600,
                42,
                1,
                0,
            ),
            (
                "2026-08-01T00:00:01Z",
                "legacy-err",
                "github",
                "repo",
                "x/y",
                "{}",
                "miss",
                3600,
                12,
                0,
                1,
            ),
        ],
    )

    store = Storage(path=path, ttl_seconds=3600)
    data = store.ledger(limit=100)
    assert data["summary"]["attempts"] == 2
    assert data["summary"]["unclassified"] == 2
    assert data["summary"]["provider_calls"] == 0
    assert data["summary"]["unknown_provider_call_states"] == 2
    for entry in data["entries"]:
        assert entry["outcome"] == "unknown"
        assert entry["provider_called"] is None
        assert entry["error_codes"] is None
        assert entry["legacy"] is True
    store.close()

    conn = sqlite3.connect(str(path))
    columns = {row[1] for row in conn.execute("PRAGMA table_info(query_log)")}
    conn.close()
    assert {"outcome", "provider_called", "error_codes"} <= columns
    # rows survived migration untouched
    conn = sqlite3.connect(str(path))
    count = conn.execute("SELECT COUNT(*) FROM query_log").fetchone()[0]
    conn.close()
    assert count == 2


def test_migration_keeps_new_schema_fresh_dbs_clean(tmp_path) -> None:
    path = tmp_path / "fresh.db"
    store = Storage(path=path, ttl_seconds=3600)
    store.log_append(
        {
            "query_id": "q",
            "provider": "hn",
            "operation": "search",
            "query": "x",
            "params": {},
            "cache": "miss",
            "outcome": "provider_succeeded",
            "provider_called": True,
            "error_codes": [],
        }
    )
    entry = _entries(store)[0]
    assert entry["outcome"] == "provider_succeeded"
    assert entry["provider_called"] is True
    assert entry["legacy"] is False
    store.close()


def test_internal_failed_null_call_state_not_legacy(tmp_path) -> None:
    """A fresh internal_failed row with provider_called null is not legacy.

    The outcome column is set (internal_failed), so only pre-column legacy rows
    may read back as ``unknown``/legacy; a null call state alone must not mark a
    row as legacy.
    """
    path = tmp_path / "internal.db"
    store = Storage(path=path, ttl_seconds=3600)
    store.log_append(
        {
            "query_id": "q",
            "provider": "hn",
            "operation": "search",
            "query": "x",
            "params": {},
            "cache": "miss",
            "outcome": "internal_failed",
            "provider_called": None,
            "error_codes": ["internal"],
        }
    )
    data = store.ledger(limit=10)
    assert data["summary"]["internal_failures"] == 1
    assert data["summary"]["unknown_provider_call_states"] == 1
    assert data["summary"]["unclassified"] == 0
    entry = data["entries"][0]
    assert entry["outcome"] == "internal_failed"
    assert entry["provider_called"] is None
    assert entry["legacy"] is False
    store.close()
