from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import platformdirs
from pydantic import BaseModel, Field, PrivateAttr


def _expand(path: str) -> Path:
    return Path(os.path.expandvars(os.path.expanduser(path)))


class HttpSettings(BaseModel):
    timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 10.0
    retries: int = 1


class CacheSettings(BaseModel):
    enabled: bool = True
    path: str = ""
    ttl_seconds: int = 3600


class GithubSettings(BaseModel):
    gh_path: str = "gh"
    timeout_seconds: float = 60.0


class HNSettings(BaseModel):
    base_url: str = "https://hn.algolia.com/api/v1"
    timeout_seconds: float = 30.0


class ExaSettings(BaseModel):
    base_url: str = "https://api.exa.ai"
    api_key_env: str = "SIFTLINE_EXA_API_KEY"
    timeout_seconds: float = 30.0


class TavilySettings(BaseModel):
    base_url: str = "https://api.tavily.com"
    api_key_env: str = "SIFTLINE_TAVILY_API_KEY"
    timeout_seconds: float = 30.0


class OpenaiWebSettings(BaseModel):
    base_url: str = "https://api.openai.com/v1"
    endpoint: str = ""
    api_key_env: str = "SIFTLINE_OPENAI_API_KEY"
    model: str = "gpt-4o-mini"
    timeout_seconds: float = 60.0
    max_results: int = 5


class ProviderSettings(BaseModel):
    github: GithubSettings = Field(default_factory=GithubSettings)
    hn: HNSettings = Field(default_factory=HNSettings)
    exa: ExaSettings = Field(default_factory=ExaSettings)
    tavily: TavilySettings = Field(default_factory=TavilySettings)
    openai_web: OpenaiWebSettings = Field(default_factory=OpenaiWebSettings)


class Config(BaseModel):
    http: HttpSettings = Field(default_factory=HttpSettings)
    cache: CacheSettings = Field(default_factory=CacheSettings)
    providers: ProviderSettings = Field(default_factory=ProviderSettings)

    _path: Path | None = PrivateAttr(default=None)
    _cache_path: Path = PrivateAttr(default_factory=lambda: Path("."))

    @classmethod
    def load(cls, explicit: str | None = None) -> Config:
        path = cls._resolve_path(explicit)
        data: dict[str, Any] = {}
        if path and path.exists():
            with path.open("rb") as fh:
                import tomllib

                data = tomllib.load(fh)
        cfg = cls.model_validate(data)
        cfg._path = path
        cfg._finalize()
        return cfg

    @classmethod
    def _resolve_path(cls, explicit: str | None) -> Path | None:
        if explicit:
            return _expand(explicit)
        env = os.environ.get("SIFTLINE_CONFIG")
        if env:
            return _expand(env)
        return Path(platformdirs.user_config_dir("siftline")) / "config.toml"

    def _finalize(self) -> None:
        raw = self.cache.path.strip()
        if raw:
            p = _expand(raw)
            if not p.is_absolute():
                base = self._path.parent if self._path else Path.cwd()
                p = base / p
        else:
            p = Path(platformdirs.user_cache_dir("siftline")) / "cache.db"
        self._cache_path = p

    @property
    def config_path(self) -> Path | None:
        return self._path

    @property
    def cache_path(self) -> Path:
        return self._cache_path
