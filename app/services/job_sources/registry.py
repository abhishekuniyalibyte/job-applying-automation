from app.config import Settings
from app.services.cache import ApiCacheService
from app.services.job_sources.adzuna import AdzunaSource
from app.services.job_sources.base import JobSource, JobSourceError
from app.services.job_sources.greenhouse import GreenhouseSource
from app.services.job_sources.lever import LeverSource


def get_search_source(name: str, settings: Settings, cache: ApiCacheService | None) -> JobSource:
    if name == "adzuna":
        return AdzunaSource(
            settings.adzuna_app_id or "", settings.adzuna_app_key or "", settings.adzuna_country, cache=cache
        )
    raise JobSourceError(f"Unknown search source '{name}' (supported: adzuna)")


def get_ats_source(ats_type: str, cache: ApiCacheService | None):
    if ats_type == "greenhouse":
        return GreenhouseSource(cache=cache)
    if ats_type == "lever":
        return LeverSource(cache=cache)
    raise JobSourceError(f"Unknown ATS type '{ats_type}' (supported: greenhouse, lever)")
