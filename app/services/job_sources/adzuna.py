from datetime import datetime

from app.schemas.job import JobQuery, NormalizedJob
from app.services.job_sources.base import JobSource, JobSourceError

CURRENCY_BY_COUNTRY = {
    "gb": "GBP", "us": "USD", "in": "INR", "au": "AUD", "ca": "CAD", "de": "EUR", "fr": "EUR",
    "nl": "EUR", "it": "EUR", "es": "EUR", "at": "EUR", "be": "EUR", "pl": "PLN", "br": "BRL",
    "mx": "MXN", "nz": "NZD", "sg": "SGD", "za": "ZAR", "ch": "CHF",
}


def _looks_remote(*texts: str | None) -> bool | None:
    blob = " ".join(t for t in texts if t).lower()
    if not blob:
        return None
    return True if "remote" in blob or "work from home" in blob else None


def parse_adzuna_result(r: dict, country: str = "gb") -> NormalizedJob:
    posted_at = None
    if r.get("created"):
        try:
            posted_at = datetime.fromisoformat(r["created"].replace("Z", "+00:00"))
        except ValueError:
            posted_at = None
    salary_min = r.get("salary_min")
    salary_max = r.get("salary_max")
    if str(r.get("salary_is_predicted", "0")) == "1":
        # Predicted salaries are estimates, not stated by the employer; keep but mark in raw.
        pass
    title = r.get("title") or ""
    location = (r.get("location") or {}).get("display_name")
    description = r.get("description") or ""
    employment_type = r.get("contract_time") or r.get("contract_type")
    return NormalizedJob(
        source="adzuna",
        source_job_id=str(r["id"]),
        title=title,
        company_name=(r.get("company") or {}).get("display_name"),
        location=location,
        description=description,
        salary_min=float(salary_min) if salary_min else None,
        salary_max=float(salary_max) if salary_max else None,
        salary_currency=CURRENCY_BY_COUNTRY.get(country.lower()) if (salary_min or salary_max) else None,
        remote=_looks_remote(title, location, description[:500]),
        employment_type=employment_type,
        posted_at=posted_at,
        # Adzuna gives an aggregator redirect, never a verified employer apply link.
        source_url=r.get("redirect_url"),
        apply_url=None,
        apply_url_verified=False,
        raw={
            "category": (r.get("category") or {}).get("label"),
            "salary_is_predicted": r.get("salary_is_predicted"),
            "adref": r.get("adref"),
            "latitude": r.get("latitude"),
            "longitude": r.get("longitude"),
        },
    )


class AdzunaSource(JobSource):
    name = "adzuna"
    BASE = "https://api.adzuna.com/v1/api/jobs"

    def __init__(self, app_id: str, app_key: str, country: str = "gb", **kwargs):
        super().__init__(**kwargs)
        if not app_id or not app_key:
            raise JobSourceError("Adzuna credentials are missing (ADZUNA_APP_ID / ADZUNA_APP_KEY)")
        self.app_id = app_id
        self.app_key = app_key
        self.country = country.lower()

    def search(self, query: JobQuery) -> list[NormalizedJob]:
        jobs: list[NormalizedJob] = []
        for page in range(1, query.max_pages + 1):
            params: dict = {
                "app_id": self.app_id,
                "app_key": self.app_key,
                "what": query.what,
                "results_per_page": query.results_per_page,
                "content-type": "application/json",
            }
            if query.where:
                params["where"] = query.where
            if query.max_days_old:
                params["max_days_old"] = query.max_days_old
            if query.salary_min:
                params["salary_min"] = int(query.salary_min)
            if query.full_time is True:
                params["full_time"] = 1
            url = f"{self.BASE}/{self.country}/search/{page}"
            cache_params = {k: v for k, v in params.items() if k not in ("app_id", "app_key")}
            data = self._get_json(url, params, cache_params=cache_params)
            results = data.get("results", []) if isinstance(data, dict) else []
            if not results:
                break
            jobs.extend(parse_adzuna_result(r, self.country) for r in results)
            if len(results) < query.results_per_page:
                break
        return jobs
