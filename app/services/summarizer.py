"""Per-job structured summary + embedding, cached in PostgreSQL."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.llm.base import LLMProvider
from app.llm.prompts import JOB_SUMMARY_SYSTEM
from app.models import Job
from app.schemas.job import JobSummary
from app.services.text_builders import job_summary_text

MAX_DESCRIPTION_CHARS = 12_000


def summarize_job(llm: LLMProvider, job: Job) -> JobSummary:
    user = (
        f"TITLE: {job.title}\nCOMPANY: {job.company_name or 'unknown'}\nLOCATION: {job.location or 'unknown'}\n"
        f"REMOTE FLAG: {job.remote}\n\nDESCRIPTION:\n{(job.description or '')[:MAX_DESCRIPTION_CHARS]}"
    )
    summary = llm.complete_structured(JOB_SUMMARY_SYSTEM, user, JobSummary)
    if not summary.role_title:
        summary.role_title = job.title
    return summary


def summarize_and_embed_jobs(
    db: Session, llm: LLMProvider, job_ids: list[int] | None = None, limit: int | None = None, batch_size: int = 50
) -> int:
    """Summarise and embed every active, non-duplicate job that has no embedding yet. Returns count processed."""
    stmt = select(Job).where(Job.is_active.is_(True), Job.duplicate_of_id.is_(None), Job.summary_embedding.is_(None))
    if job_ids is not None:
        stmt = stmt.where(Job.id.in_(job_ids))
    if limit:
        stmt = stmt.limit(limit)
    jobs = db.scalars(stmt).all()
    processed = 0
    for i in range(0, len(jobs), batch_size):
        batch = jobs[i : i + batch_size]
        texts: list[str] = []
        for job in batch:
            if job.summary and job.summary_text:
                texts.append(job.summary_text)  # summary cached, only embedding missing
                continue
            summary = summarize_job(llm, job)
            job.summary = summary.model_dump()
            job.summary_text = job_summary_text(summary)
            job.summary_model = f"{llm.name}:{llm.chat_model}"
            texts.append(job.summary_text)
        vectors = llm.embed(texts)
        for job, vec in zip(batch, vectors, strict=True):
            job.summary_embedding = vec
            processed += 1
        db.commit()
    return processed
