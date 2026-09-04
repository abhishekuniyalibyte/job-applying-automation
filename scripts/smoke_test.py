"""End-to-end smoke test against a real PostgreSQL+pgvector database, using the offline fake LLM and
stubbed Adzuna / Greenhouse responses. No API keys required.

    DATABASE_URL=postgresql+psycopg://jobs:jobs@localhost:5432/jobs python scripts/smoke_test.py
"""

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

os.environ["LLM_PROVIDER"] = "fake"
os.environ.setdefault("ADZUNA_APP_ID", "dummy")
os.environ.setdefault("ADZUNA_APP_KEY", "dummy")

from fastapi.testclient import TestClient  # noqa: E402

from app.llm import get_llm  # noqa: E402
from app.main import app  # noqa: E402
from app.schemas.analysis import JobMatchAnalysis  # noqa: E402
from app.schemas.candidate import CandidateProfile, EducationEntry, ExperienceEntry  # noqa: E402
from app.schemas.job import JobSummary  # noqa: E402
from app.schemas.resume import TailoredResume  # noqa: E402
from app.services.job_sources import base  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ADZUNA_PAGE = json.loads((ROOT / "tests/fixtures/adzuna_page.json").read_text())

RESUME_TXT = """Jane Doe
jane@example.com | London
Senior Backend Engineer, Acme Ltd, Jan 2021 - Present
- Built FastAPI services handling 2M requests/day on PostgreSQL
- Led migration to Kubernetes, cutting deploy time by 40%
Backend Engineer, Beta Inc, 2018 - 2020
- Maintained Django monolith and Celery workers
Education: BSc Computer Science, University of Leeds, 2014 - 2018
Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes, Django, Celery, Redis
"""


# --- fake LLM handlers ---------------------------------------------------------------------------
def parse_profile(_system: str, _user: str) -> CandidateProfile:
    return CandidateProfile(
        full_name="Jane Doe", email="jane@example.com", location="London", seniority="senior",
        years_of_experience=6, target_roles=["Backend Engineer"],
        skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Django", "Celery", "Redis"],
        experience=[
            ExperienceEntry(company="Acme Ltd", title="Senior Backend Engineer", start_date="Jan 2021",
                            end_date="Present", bullets=["Built FastAPI services handling 2M requests/day on PostgreSQL",
                                                         "Led migration to Kubernetes, cutting deploy time by 40%"]),
            ExperienceEntry(company="Beta Inc", title="Backend Engineer", start_date="2018", end_date="2020",
                            bullets=["Maintained Django monolith and Celery workers"]),
        ],
        education=[EducationEntry(institution="University of Leeds", degree="BSc", field_of_study="Computer Science",
                                  start_date="2014", end_date="2018")],
    )


def summarize(_system: str, user: str) -> JobSummary:
    title = re.search(r"TITLE: (.*)", user).group(1)
    skills = [s for s in ["Python", "FastAPI", "PostgreSQL", "SQL", "Excel", "Kubernetes"] if s.lower() in user.lower()]
    return JobSummary(role_title=title, seniority="senior" if "senior" in title.lower() else "mid",
                      required_skills=skills, one_line=f"{title} role")


def analyze(_system: str, user: str) -> JobMatchAnalysis:
    backend = "backend" in user.split("JOB:", 1)[1].lower()
    return JobMatchAnalysis(match_score=85 if backend else 20, matched_skills=["Python"] if backend else [],
                            missing_skills=[] if backend else ["Excel"], experience_compatibility="strong",
                            location_compatibility="match", explanation="stub")


def tailor(_system: str, _user: str) -> TailoredResume:
    p = parse_profile("", "")
    return TailoredResume(summary="Senior backend engineer with Python, FastAPI and PostgreSQL.",
                          skills=["Python", "FastAPI", "PostgreSQL", "Kubernetes"],
                          experience=[p.experience[0]], education=p.education,
                          tailoring_notes=["Put FastAPI/PostgreSQL first"])


get_llm().handlers = {CandidateProfile: parse_profile, JobSummary: summarize,
                      JobMatchAnalysis: analyze, TailoredResume: tailor}

# --- stub external HTTP at the transport level so the DB-level api_cache is really exercised ------
import httpx  # noqa: E402

adzuna_calls = {"n": 0}
GREENHOUSE_BOARD = {"jobs": [{
    "id": 999, "title": "Senior Backend Engineer (Python)", "absolute_url": "https://boards.greenhouse.io/acme/jobs/999",
    "location": {"name": "London, UK"}, "content": "<p>Python, FastAPI, PostgreSQL</p>", "updated_at": "2026-09-01T00:00:00Z",
}]}
greenhouse_board = {"data": GREENHOUSE_BOARD}


def _handler(request: httpx.Request) -> httpx.Response:
    url = str(request.url)
    if "adzuna.com" in url:
        adzuna_calls["n"] += 1
        return httpx.Response(200, json=ADZUNA_PAGE if "/search/1?" in url else {"results": []})
    if "greenhouse.io" in url:
        return httpx.Response(200, json=greenhouse_board["data"])
    return httpx.Response(404, json={"error": "unexpected url " + url})


_RealClient = httpx.Client
base.httpx.Client = lambda **kw: _RealClient(transport=httpx.MockTransport(_handler), **kw)


def check(cond, msg):
    if not cond:
        raise SystemExit(f"FAIL: {msg}")
    print(f"ok   {msg}")


with TestClient(app) as c:
    r = c.post("/users", json={"email": "jane@example.com", "preferences": {"role": "backend engineer"}})
    check(r.status_code == 200, f"create user -> {r.json()}")
    user_id = r.json()["id"]

    # PDF upload (generated with PyMuPDF) exercises text extraction
    import pymupdf
    doc = pymupdf.open()
    page = doc.new_page()
    page.insert_text((50, 72), RESUME_TXT, fontsize=9)
    pdf_bytes = doc.tobytes()
    r = c.post("/resumes/upload", data={"user_id": user_id}, files={"file": ("resume.pdf", pdf_bytes, "application/pdf")})
    check(r.status_code == 200 and r.json()["has_embedding"], "resume upload (PDF) parsed + embedded")
    check(r.json()["profile"]["full_name"] == "Jane Doe", "profile structured")
    resume_id = r.json()["id"]

    q = {"source": "adzuna", "query": {"what": "backend engineer", "where": "London", "max_pages": 2}}
    r = c.post("/jobs/ingest", json=q)
    run = r.json()
    check(run["status"] == "completed" and run["inserted"] == 2 and run["updated"] == 0, f"adzuna ingest #1 {run}")
    r = c.post("/jobs/ingest", json=q)
    run = r.json()
    check(run["inserted"] == 0 and run["updated"] == 2, f"adzuna ingest #2 idempotent {run}")
    check(adzuna_calls["n"] == 1, f"second ingest served from api_cache (HTTP calls={adzuna_calls['n']})")

    r = c.get("/jobs")
    jobs = r.json()
    check(len(jobs) == 2, "two active jobs listed")
    check(all(j["apply_url"] is None and not j["apply_url_verified"] and j["source_url"] for j in jobs),
          "adzuna jobs expose redirect only, no verified apply link")

    r = c.post("/matches/rank", json={"resume_id": resume_id, "filters": {"max_days_old": 60}, "top_k": 10})
    ranked = r.json()
    check(r.status_code == 200 and len(ranked) == 2, "ranked shortlist")
    check("Backend" in ranked[0]["job"]["title"], f"backend job ranks first (sim={ranked[0]['similarity']:.3f})")
    check(all(j["job"]["summary"] for j in ranked), "summaries cached on jobs")

    r = c.post("/matches/rank", json={"resume_id": resume_id, "filters": {"salary_min": 80000}, "top_k": 10})
    check([j["job"]["title"] for j in r.json()] == ["Senior Backend Engineer (Python)", "Data Analyst"] or len(r.json()) == 2,
          "salary filter keeps jobs without salary eligible")
    r = c.post("/matches/rank", json={"resume_id": resume_id, "filters": {"salary_min": 95000, "require_salary": True}})
    check(r.json() == [], "require_salary + high min excludes everything")

    r = c.post("/matches/analyze", json={"resume_id": resume_id})
    analyses = r.json()
    check(len(analyses) == 2 and analyses[0]["analysis"]["match_score"] == 85, "LLM analysis of shortlist")
    best_job_id = analyses[0]["job"]["id"]
    r = c.get(f"/matches/{resume_id}?min_score=50")
    check(len(r.json()) == 1, "matches listing filtered by score")

    r = c.post("/tailor", json={"resume_id": resume_id, "job_id": best_job_id})
    t = r.json()
    check(r.status_code == 200 and t["verification_status"] == "verified", f"tailored resume verified {t['verification_issues']}")
    check(t["markdown"].startswith("# Jane Doe"), "markdown rendered")

    r = c.get(f"/jobs/{best_job_id}?resume_id={resume_id}")
    d = r.json()
    check(d["analysis"]["match_score"] == 85 and d["tailored_resume"]["id"] == t["id"], "job detail bundles analysis + tailored resume")
    check(d["application"]["apply_url"] is None and d["application"]["source_url"], "application block separates redirect")

    # Greenhouse board for the same company/title/location -> verified apply link + dedupe
    r = c.post("/companies", json={"name": "Acme Ltd", "ats_type": "greenhouse", "ats_slug": "acme"})
    company_id = r.json()["id"]
    r = c.post(f"/companies/{company_id}/ingest")
    run = r.json()
    check(run["status"] == "completed" and run["inserted"] == 1 and run["duplicates"] == 1, f"greenhouse ingest {run}")
    r = c.get("/jobs?include_duplicates=true")
    by_source = {j["source"]: j for j in r.json() if "Backend" in j["title"]}
    gh, adz = by_source["greenhouse"], by_source["adzuna"]
    check(gh["apply_url_verified"] and gh["apply_url"].startswith("https://boards.greenhouse.io/"), "ATS job has verified apply_url")
    check(adz["duplicate_of_id"] == gh["id"] and gh["duplicate_of_id"] is None, "adzuna copy linked to verified ATS canonical")
    r = c.get("/jobs")
    check(all(j["duplicate_of_id"] is None for j in r.json()) and len(r.json()) == 2, "default listing hides duplicates")

    # Board now empty -> posting marked inactive, never deleted
    greenhouse_board["data"] = {"jobs": []}
    r = c.post(f"/companies/{company_id}/ingest")
    check(r.json()["fetched"] == 1, "repeat board fetch within TTL served from api_cache")
    r = c.post(f"/companies/{company_id}/ingest?refresh=true")
    check(r.json()["fetched"] == 0, "refresh=true bypasses api_cache")
    r = c.get("/jobs?active_only=false&include_duplicates=true")
    gh_after = next(j for j in r.json() if j["id"] == gh["id"])
    check(gh_after["is_active"] is False, "closed ATS posting deactivated, still stored")

    r = c.get("/jobs/runs")
    check(len(r.json()) == 5, "ingestion runs recorded")

print("\nSMOKE TEST PASSED")
