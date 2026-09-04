import html
import re
from datetime import datetime

from app.schemas.job import JobQuery, NormalizedJob
from app.services.job_sources.base import JobSource

_TAG = re.compile(r"<[^>]+>")


def html_to_text(s: str | None) -> str:
    if not s:
        return ""
    text = html.unescape(s)
    text = re.sub(r"</(p|div|li|br|h\d)>", "\n", text, flags=re.I)
    text = _TAG.sub(" ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"[ \t]*\n[ \t]*", "\n", text)
    return re.sub(r"\n{2,}", "\n", text).strip()


def parse_greenhouse_job(j: dict, company_name: str) -> NormalizedJob:
    posted_at = None
    for key in ("first_published", "updated_at"):
        if j.get(key):
            try:
                posted_at = datetime.fromisoformat(j[key].replace("Z", "+00:00"))
                break
            except ValueError:
                continue
    location = (j.get("location") or {}).get("name")
    title = j.get("title") or ""
    description = html_to_text(j.get("content"))
    url = j.get("absolute_url")
    return NormalizedJob(
        source="greenhouse",
        source_job_id=str(j["id"]),
        title=title,
        company_name=company_name,
        location=location,
        description=description,
        remote=True if "remote" in f"{title} {location or ''}".lower() else None,
        posted_at=posted_at,
        source_url=url,
        apply_url=url,
        apply_url_verified=bool(url),
        raw={"departments": [d.get("name") for d in j.get("departments", []) if isinstance(d, dict)]},
    )


class GreenhouseSource(JobSource):
    name = "greenhouse"
    BASE = "https://boards-api.greenhouse.io/v1/boards"

    def search(self, query: JobQuery) -> list[NormalizedJob]:
        raise NotImplementedError("Greenhouse has no global search; use fetch_board(slug, company_name)")

    def fetch_board(self, slug: str, company_name: str) -> list[NormalizedJob]:
        data = self._get_json(f"{self.BASE}/{slug}/jobs", {"content": "true"})
        return [parse_greenhouse_job(j, company_name) for j in (data or {}).get("jobs", [])]
