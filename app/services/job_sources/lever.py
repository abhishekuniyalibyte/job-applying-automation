from datetime import UTC, datetime

from app.schemas.job import JobQuery, NormalizedJob
from app.services.job_sources.base import JobSource


def parse_lever_posting(p: dict, company_name: str) -> NormalizedJob:
    posted_at = None
    if p.get("createdAt"):
        posted_at = datetime.fromtimestamp(int(p["createdAt"]) / 1000, tz=UTC)
    cats = p.get("categories") or {}
    location = cats.get("location")
    workplace = (p.get("workplaceType") or "").lower()
    title = p.get("text") or ""
    apply_url = p.get("applyUrl") or p.get("hostedUrl")
    description = p.get("descriptionPlain") or ""
    for lst in p.get("lists", []) or []:
        description += f"\n{lst.get('text', '')}\n" + (lst.get("content") or "")
    return NormalizedJob(
        source="lever",
        source_job_id=str(p["id"]),
        title=title,
        company_name=company_name,
        location=location,
        description=description,
        remote=True if workplace == "remote" or "remote" in (location or "").lower() else None,
        employment_type=cats.get("commitment"),
        posted_at=posted_at,
        source_url=p.get("hostedUrl"),
        apply_url=apply_url,
        apply_url_verified=bool(apply_url),
        raw={"team": cats.get("team"), "department": cats.get("department"), "workplaceType": workplace or None},
    )


class LeverSource(JobSource):
    name = "lever"
    BASE = "https://api.lever.co/v0/postings"

    def search(self, query: JobQuery) -> list[NormalizedJob]:
        raise NotImplementedError("Lever has no global search; use fetch_board(slug, company_name)")

    def fetch_board(self, slug: str, company_name: str) -> list[NormalizedJob]:
        data = self._get_json(f"{self.BASE}/{slug}", {"mode": "json"})
        return [parse_lever_posting(p, company_name) for p in (data or [])]
