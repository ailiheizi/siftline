from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from siftline.config import Config


def test_defaults_with_clean_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = Config.load()
    assert cfg.cache.ttl_seconds == 3600
    assert cfg.http.timeout_seconds == 30.0
    assert cfg.providers.openai_web.model == "gpt-4o-mini"
    assert cfg.cache_path.is_absolute()
    assert str(tmp_path) in str(cfg.cache_path)
    assert cfg.config_path is not None


def test_load_explicit_file(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        "[http]\ntimeout_seconds = 5.0\n\n[providers.openai_web]\nmodel = 'custom-model'\n\n"
        "[cache]\nttl_seconds = 60\n"
    )
    cfg = Config.load(str(path))
    assert cfg.http.timeout_seconds == 5.0
    assert cfg.providers.openai_web.model == "custom-model"
    assert cfg.cache.ttl_seconds == 60
    assert cfg.config_path == path


def test_siftline_config_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "conf.toml"
    path.write_text("[cache]\nttl_seconds = 10\n")
    monkeypatch.setenv("SIFTLINE_CONFIG", str(path))
    cfg = Config.load()
    assert cfg.cache.ttl_seconds == 10


def test_relative_cache_path_resolved_against_config_dir(tmp_path) -> None:
    path = tmp_path / "cfg" / "config.toml"
    path.parent.mkdir()
    path.write_text("[cache]\npath = 'var/cache.db'\n")
    cfg = Config.load(str(path))
    assert cfg.cache_path == path.parent / "var" / "cache.db"


def test_tilde_expansion(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    path = tmp_path / "config.toml"
    path.write_text("[cache]\npath = '~/custom/cache.db'\n")
    cfg = Config.load(str(path))
    assert cfg.cache_path == Path.home() / "custom" / "cache.db"


def test_invalid_toml_raises(tmp_path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("not [valid toml")
    with pytest.raises(tomllib.TOMLDecodeError):
        Config.load(str(path))
