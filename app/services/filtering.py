"""Cheap local filtering applied before embeddings/LLM."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_

from app.models import Job
from app.schemas.job import JobFilters


def filter_conditions(f: JobFilters):
    """SQLAlchemy conditions equivalent to `job_passes_filters`."""
    conds = [Job.is_active.is_(True), Job.duplicate_of_id.is_(None)]
    if f.max_days_old:
        cutoff = datetime.now(UTC) - timedelta(days=f.max_days_old)
        # Unknown posting date: fall back to when we first saw it
        conds.append(or_(Job.posted_at >= cutoff, and_(Job.posted_at.is_(None), Job.first_seen_at >= cutoff)))
    if f.salary_min is not None:
        best = Job.salary_max
        has_salary = or_(Job.salary_max.isnot(None), Job.salary_min.isnot(None))
        meets = or_(best >= f.salary_min, and_(Job.salary_max.is_(None), Job.salary_min >= f.salary_min))
        conds.append(and_(has_salary, meets) if f.require_salary else or_(~has_salary, meets))
    elif f.require_salary:
        conds.append(or_(Job.salary_max.isnot(None), Job.salary_min.isnot(None)))
    if f.location_contains:
        conds.append(or_(Job.location.ilike(f"%{f.location_contains}%"), Job.remote.is_(True)))
    if f.remote_only:
        conds.append(Job.remote.is_(True))
    for kw in f.exclude_title_keywords:
        conds.append(~Job.title.ilike(f"%{kw}%"))
    if f.include_title_keywords:
        conds.append(or_(*[Job.title.ilike(f"%{kw}%") for kw in f.include_title_keywords]))
    if f.sources:
        conds.append(Job.source.in_(f.sources))
    return conds


def job_passes_filters(job, f: JobFilters, now: datetime | None = None) -> bool:
    """Pure-Python twin of filter_conditions (used for tests and in-memory lists)."""
    now = now or datetime.now(UTC)
    if not job.is_active or job.duplicate_of_id is not None:
        return False
    if f.max_days_old:
        cutoff = now - timedelta(days=f.max_days_old)
        ref = job.posted_at or job.first_seen_at
        if ref is None or ref < cutoff:
            return False
    has_salary = job.salary_max is not None or job.salary_min is not None
    if f.salary_min is not None:
        best = job.salary_max if job.salary_max is not None else job.salary_min
        if has_salary:
            if best < f.salary_min:
                return False
        elif f.require_salary:
            return False
    elif f.require_salary and not has_salary:
        return False
    if f.location_contains:
        loc_ok = job.location and f.location_contains.lower() in job.location.lower()
        if not loc_ok and job.remote is not True:
            return False
    if f.remote_only and job.remote is not True:
        return False
    title = (job.title or "").lower()
    if any(kw.lower() in title for kw in f.exclude_title_keywords):
        return False
    if f.include_title_keywords and not any(kw.lower() in title for kw in f.include_title_keywords):
        return False
    if f.sources and job.source not in f.sources:
        return False
    return True
