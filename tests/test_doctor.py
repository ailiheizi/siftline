from __future__ import annotations

from siftline.doctor import provider_statuses, run_checks


def test_run_checks_structure(config, storage) -> None:
    report = run_checks(config, storage, network=False)
    assert report["summary"]["ok"] >= 1
    names = {c["check"] for c in report["checks"]}
    assert {"python", "config", "cache", "key_exa", "key_tavily", "key_openai_web"} <= names
    for check in report["checks"]:
        assert check["status"] in ("ok", "warn", "error", "unknown")


def test_run_checks_missing_keys(config, storage) -> None:
    report = run_checks(config, storage, network=False)
    key_checks = {c["check"]: c["status"] for c in report["checks"]}
    assert key_checks["key_exa"] == "error"
    assert key_checks["key_tavily"] == "error"
    assert key_checks["key_openai_web"] == "error"


def test_run_checks_with_keys(config, storage, monkeypatch) -> None:
    monkeypatch.setenv("SIFTLINE_EXA_API_KEY", "x")
    monkeypatch.setenv("TAVILY_API_KEY", "y")
    monkeypatch.setenv("OPENAI_API_KEY", "z")
    report = run_checks(config, storage, network=False)
    key_checks = {c["check"]: c["status"] for c in report["checks"]}
    assert key_checks["key_exa"] == "ok"
    assert key_checks["key_tavily"] == "ok"
    assert key_checks["key_openai_web"] == "ok"


def test_provider_statuses(config) -> None:
    statuses = {s["name"]: s for s in provider_statuses(config)}
    assert statuses["hn"]["requires_key"] is False
    assert statuses["exa"]["key_present"] is False
    assert statuses["web"]["detail"] == "model=gpt-4o-mini"
