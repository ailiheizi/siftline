from __future__ import annotations

from typing import Any

from ..config import Config
from ..storage import Storage
from .base import BaseProvider
from .exa import ExaProvider
from .github import GithubProvider
from .hn import HNProvider
from .openai_web import OpenAIWebProvider
from .tavily import TavilyProvider

_PROVIDERS: dict[str, type[BaseProvider]] = {
    "github": GithubProvider,
    "hn": HNProvider,
    "exa": ExaProvider,
    "tavily": TavilyProvider,
    "web": OpenAIWebProvider,
}

PROVIDER_NAMES = list(_PROVIDERS)


def get_provider(
    name: str,
    config: Config,
    storage: Storage,
    http_transport: Any | None = None,
) -> BaseProvider:
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"unknown provider: {name}")
    return cls(config, storage, http_transport=http_transport)
