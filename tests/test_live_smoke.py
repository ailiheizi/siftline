from __future__ import annotations

import json
import os
import shutil
import subprocess

import pytest
from typer.testing import CliRunner

from siftline.cli import app

pytestmark = pytest.mark.live

runner = CliRunner()


def _gh_ready() -> bool:
    if os.environ.get("SIFTLINE_SKIP_LIVE"):
        return False
    gh = shutil.which("gh")
    if not gh:
        return False
    try:
        proc = subprocess.run([gh, "auth", "status"], capture_output=True, text=True, timeout=15)
        return proc.returncode == 0
    except Exception:
        return False


def _config(tmp_path) -> str:
    path = tmp_path / "config.toml"
    path.write_text("[cache]\npath = 'live.db'\nttl_seconds = 60\n")
    return str(path)


@pytest.mark.skipif(not _gh_ready(), reason="gh CLI not installed or not authenticated")
def test_live_github_search_repos(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            _config(tmp_path),
            "--format",
            "json",
            "github",
            "search-repos",
            "siftline in:name",
            "--limit",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["schema_version"] == "1"
    assert payload["provider"] == "github"
    assert payload["errors"] == []
    assert isinstance(payload["items"], list)


@pytest.mark.skipif(not _gh_ready(), reason="gh CLI not installed or not authenticated")
def test_live_github_repo_metadata(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            _config(tmp_path),
            "--format",
            "json",
            "github",
            "repo",
            "octocat/Hello-World",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert len(payload["items"]) == 1
    assert "Hello-World" in payload["items"][0]["title"]


@pytest.mark.skipif(os.environ.get("SIFTLINE_SKIP_LIVE"), reason="live tests disabled")
def test_live_hn_search(tmp_path) -> None:
    result = runner.invoke(
        app,
        [
            "--config",
            _config(tmp_path),
            "--format",
            "json",
            "hn",
            "search",
            "llm agents",
            "--limit",
            "3",
        ],
    )
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["provider"] == "hn"
    assert payload["errors"] == []
    assert len(payload["items"]) <= 3
