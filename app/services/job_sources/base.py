from abc import ABC, abstractmethod
from typing import Any

import httpx

from app.schemas.job import JobQuery, NormalizedJob
from app.services.cache import ApiCacheService


class JobSourceError(RuntimeError):
    pass


class JobSource(ABC):
    name: str = "base"

    def __init__(self, cache: ApiCacheService | None = None, client: httpx.Client | None = None):
        self.cache = cache
        self.client = client or httpx.Client(timeout=30.0, headers={"User-Agent": "job-assistant/0.1"})

    @abstractmethod
    def search(self, query: JobQuery) -> list[NormalizedJob]: ...

    def _get_json(self, url: str, params: dict[str, Any], cache_params: dict[str, Any] | None = None) -> Any:
        """GET JSON with database-level caching keyed on (source, cache_params or params)."""
        key_params = {"url": url, **(cache_params if cache_params is not None else params)}
        if self.cache is not None:
            cached = self.cache.get(self.name, key_params)
            if cached is not None:
                return cached.get("data")
        try:
            resp = self.client.get(url, params=params)
            resp.raise_for_status()
        except httpx.HTTPError as err:
            raise JobSourceError(f"{self.name}: request failed: {err}") from err
        data = resp.json()
        if self.cache is not None:
            self.cache.set(self.name, key_params, {"data": data})
        return data
