from __future__ import annotations

import pytest

from siftline.config import Config
from siftline.storage import Storage

_ENV_KEYS = (
    "SIFTLINE_EXA_API_KEY",
    "SIFTLINE_TAVILY_API_KEY",
    "SIFTLINE_OPENAI_API_KEY",
    "EXA_API_KEY",
    "TAVILY_API_KEY",
    "OPENAI_API_KEY",
    "SIFTLINE_CONFIG",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


@pytest.fixture
def config(tmp_path) -> Config:
    return Config.model_validate(
        {"cache": {"path": str(tmp_path / "cache.db"), "ttl_seconds": 3600}}
    )


@pytest.fixture
def storage(tmp_path):
    store = Storage(path=tmp_path / "cache.db", ttl_seconds=3600, enabled=True)
    yield store
    store.close()
