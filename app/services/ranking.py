"""Semantic shortlist: candidate embedding vs. job summary embeddings via pgvector cosine distance."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Job, Resume
from app.schemas.job import JobFilters
from app.services.filtering import filter_conditions


def rank_jobs(db: Session, resume: Resume, filters: JobFilters, top_k: int) -> list[tuple[Job, float]]:
    if resume.profile_embedding is None:
        raise ValueError("Resume has no embedding; parse it first")
    distance = Job.summary_embedding.cosine_distance(resume.profile_embedding).label("distance")
    stmt = (
        select(Job, distance)
        .where(Job.summary_embedding.isnot(None), *filter_conditions(filters))
        .order_by(distance)
        .limit(top_k)
    )
    return [(job, float(1.0 - dist)) for job, dist in db.execute(stmt).all()]
