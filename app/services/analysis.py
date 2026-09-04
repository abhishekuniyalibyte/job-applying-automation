"""LLM match analysis for a (resume, job) pair, cached in job_analyses."""

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import LLMProvider
from app.llm.prompts import JOB_ANALYSIS_SYSTEM
from app.models import Job, JobAnalysis, Resume
from app.schemas.analysis import JobMatchAnalysis
from app.services.resume_parser import get_profile

MAX_DESCRIPTION_CHARS = 8_000


def build_analysis_prompt(resume: Resume, job: Job) -> str:
    profile = get_profile(resume)
    summary = json.dumps(job.summary, indent=1) if job.summary else "n/a"
    return (
        f"CANDIDATE PROFILE (JSON):\n{profile.model_dump_json(indent=1)}\n\n"
        f"JOB:\nTitle: {job.title}\nCompany: {job.company_name}\nLocation: {job.location}\nRemote: {job.remote}\n"
        f"Salary: {job.salary_min}-{job.salary_max} {job.salary_currency or ''}\n"
        f"Structured summary: {summary}\n\nFull description:\n{(job.description or '')[:MAX_DESCRIPTION_CHARS]}"
    )


def analyze_job(db: Session, llm: LLMProvider, resume: Resume, job: Job, force: bool = False) -> JobAnalysis:
    existing = db.scalar(
        select(JobAnalysis).where(JobAnalysis.resume_id == resume.id, JobAnalysis.job_id == job.id)
    )
    if existing and not force:
        return existing
    result = llm.complete_structured(JOB_ANALYSIS_SYSTEM, build_analysis_prompt(resume, job), JobMatchAnalysis)
    row = existing or JobAnalysis(resume_id=resume.id, job_id=job.id)
    row.match_score = result.match_score
    row.matched_skills = result.matched_skills
    row.missing_skills = result.missing_skills
    row.experience_compatibility = result.experience_compatibility
    row.location_compatibility = result.location_compatibility
    row.explanation = result.explanation
    row.result = result.model_dump()
    row.model = f"{llm.name}:{llm.chat_model}"
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def analyze_jobs(db: Session, llm: LLMProvider, resume: Resume, jobs: list[Job]) -> list[JobAnalysis]:
    return [analyze_job(db, llm, resume, job) for job in jobs]


def get_analysis(db: Session, resume_id: int, job_id: int) -> JobAnalysis | None:
    return db.scalar(select(JobAnalysis).where(JobAnalysis.resume_id == resume_id, JobAnalysis.job_id == job_id))
