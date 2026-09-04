"""Idempotent job ingestion: upsert on (source, source_job_id), dedupe, freshness tracking."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import case, func, literal_column, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import Company, IngestionRun, Job
from app.schemas.job import JobQuery, NormalizedJob
from app.services.cache import ApiCacheService
from app.services.job_sources.registry import get_ats_source, get_search_source
from app.services.normalization import dedupe_key, normalize_company_name, normalize_url


def _job_row(j: NormalizedJob, now: datetime, company_id: int | None) -> dict:
    return {
        "source": j.source,
        "source_job_id": j.source_job_id,
        "company_id": company_id,
        "company_name": j.company_name,
        "title": j.title[:500],
        "location": (j.location or None) and j.location[:255],
        "description": j.description or "",
        "salary_min": j.salary_min,
        "salary_max": j.salary_max,
        "salary_currency": j.salary_currency,
        "remote": j.remote,
        "employment_type": j.employment_type,
        "posted_at": j.posted_at,
        "first_seen_at": now,
        "last_seen_at": now,
        "last_verified_at": now,
        "is_active": True,
        "source_url": j.source_url,
        "normalized_url": normalize_url(j.apply_url or j.source_url),
        "apply_url": j.apply_url if j.apply_url_verified else None,
        "apply_url_verified": bool(j.apply_url and j.apply_url_verified),
        "dedupe_key": dedupe_key(j.company_name, j.title, j.location),
        "raw": j.raw,
    }


def upsert_jobs(db: Session, jobs: list[NormalizedJob], company_id: int | None = None) -> dict:
    """Insert new jobs, refresh existing ones. Returns counts and the affected job ids."""
    now = datetime.now(UTC)
    unique: dict[tuple[str, str], NormalizedJob] = {}
    for j in jobs:
        unique[(j.source, j.source_job_id)] = j  # last write wins within a batch
    if not unique:
        return {"inserted": 0, "updated": 0, "ids": []}

    inserted = updated = 0
    ids: list[int] = []
    rows = [_job_row(j, now, company_id) for j in unique.values()]
    for i in range(0, len(rows), 200):
        chunk = rows[i : i + 200]
        stmt = pg_insert(Job).values(chunk)
        excluded = stmt.excluded
        description_changed = excluded.description != Job.description
        stmt = stmt.on_conflict_do_update(
            constraint="uq_jobs_source_source_job_id",
            set_={
                "company_id": func.coalesce(excluded.company_id, Job.company_id),
                "company_name": excluded.company_name,
                "title": excluded.title,
                "location": excluded.location,
                "description": excluded.description,
                "salary_min": excluded.salary_min,
                "salary_max": excluded.salary_max,
                "salary_currency": excluded.salary_currency,
                "remote": excluded.remote,
                "employment_type": excluded.employment_type,
                "posted_at": func.coalesce(excluded.posted_at, Job.posted_at),
                "last_seen_at": now,
                "last_verified_at": now,
                "is_active": True,
                "source_url": excluded.source_url,
                "normalized_url": excluded.normalized_url,
                "apply_url": excluded.apply_url,
                "apply_url_verified": excluded.apply_url_verified,
                "dedupe_key": excluded.dedupe_key,
                "raw": excluded.raw,
                # Invalidate the cached summary/embedding only when the description actually changed
                "summary": case((description_changed, None), else_=Job.summary),
                "summary_text": case((description_changed, None), else_=Job.summary_text),
                "summary_embedding": case((description_changed, None), else_=Job.summary_embedding),
            },
        ).returning(Job.id, literal_column("(xmax = 0)").label("inserted"))
        for job_id, was_inserted in db.execute(stmt).all():
            ids.append(job_id)
            if was_inserted:
                inserted += 1
            else:
                updated += 1
    db.commit()
    return {"inserted": inserted, "updated": updated, "ids": ids}


def mark_duplicates(db: Session, job_ids: list[int]) -> int:
    """Link jobs that share a normalised URL or company/title/location key to a canonical job."""
    if not job_ids:
        return 0
    count = 0
    jobs = db.scalars(select(Job).where(Job.id.in_(job_ids))).all()
    for job in jobs:
        if job.duplicate_of_id is not None:
            continue
        conds = []
        if job.normalized_url:
            conds.append(Job.normalized_url == job.normalized_url)
        if job.dedupe_key and job.dedupe_key.replace("|", "").strip():
            conds.append(Job.dedupe_key == job.dedupe_key)
        if not conds:
            continue
        candidates = db.scalars(
            select(Job)
            .where(Job.id != job.id, Job.is_active.is_(True), Job.duplicate_of_id.is_(None), or_(*conds))
            .order_by(Job.apply_url_verified.desc(), Job.id.asc())
        ).all()
        if not candidates:
            continue
        # Canonical = verified-apply-link job if any, else the earliest seen among job + candidates
        pool = sorted([job, *candidates], key=lambda j: (not j.apply_url_verified, j.id))
        canonical = pool[0]
        for other in pool[1:]:
            if other.duplicate_of_id is None:
                other.duplicate_of_id = canonical.id
                count += 1
    db.commit()
    return count


def deactivate_stale(db: Session, source: str, days: int) -> int:
    """Jobs from `source` not seen for `days` are marked inactive (never deleted)."""
    cutoff = datetime.now(UTC) - timedelta(days=days)
    result = db.execute(
        update(Job)
        .where(Job.source == source, Job.is_active.is_(True), Job.last_seen_at < cutoff)
        .values(is_active=False)
    )
    db.commit()
    return result.rowcount or 0


def deactivate_missing_for_company(db: Session, company_id: int, source: str, seen_ids: list[str]) -> int:
    """For full-board ATS fetches: anything on the board previously but absent now is closed."""
    stmt = update(Job).where(Job.company_id == company_id, Job.source == source, Job.is_active.is_(True))
    if seen_ids:
        stmt = stmt.where(Job.source_job_id.not_in(seen_ids))
    result = db.execute(stmt.values(is_active=False))
    db.commit()
    return result.rowcount or 0


def run_search_ingestion(
    db: Session, settings: Settings, source_name: str, query: JobQuery, refresh: bool = False
) -> IngestionRun:
    """refresh=True bypasses the DB-level API cache (forces a live fetch / re-verification)."""
    run = IngestionRun(source=source_name, params={**query.model_dump(), "refresh": refresh}, status="running")
    db.add(run)
    db.commit()
    try:
        cache = None if refresh else ApiCacheService(db, settings.api_cache_ttl_hours)
        source = get_search_source(source_name, settings, cache)
        jobs = source.search(query)
        result = upsert_jobs(db, jobs)
        dups = mark_duplicates(db, result["ids"])
        deactivate_stale(db, source_name, settings.stale_job_days)
        run.fetched = len(jobs)
        run.inserted = result["inserted"]
        run.updated = result["updated"]
        run.duplicates = dups
        run.status = "completed"
    except Exception as err:  # noqa: BLE001
        run.status = "failed"
        run.error = str(err)[:2000]
    run.finished_at = datetime.now(UTC)
    db.commit()
    return run


def run_ats_ingestion(db: Session, settings: Settings, company: Company, refresh: bool = False) -> IngestionRun:
    if not company.ats_type or not company.ats_slug:
        raise ValueError(f"Company {company.name} has no ATS configured")
    run = IngestionRun(
        source=company.ats_type,
        params={"company_id": company.id, "ats_slug": company.ats_slug, "refresh": refresh},
        status="running",
    )
    db.add(run)
    db.commit()
    try:
        cache = None if refresh else ApiCacheService(db, settings.api_cache_ttl_hours)
        source = get_ats_source(company.ats_type, cache)
        jobs = source.fetch_board(company.ats_slug, company.name)
        result = upsert_jobs(db, jobs, company_id=company.id)
        dups = mark_duplicates(db, result["ids"])
        deactivate_missing_for_company(db, company.id, company.ats_type, [j.source_job_id for j in jobs])
        run.fetched = len(jobs)
        run.inserted = result["inserted"]
        run.updated = result["updated"]
        run.duplicates = dups
        run.status = "completed"
    except Exception as err:  # noqa: BLE001
        run.status = "failed"
        run.error = str(err)[:2000]
    run.finished_at = datetime.now(UTC)
    db.commit()
    return run


def get_or_create_company(db: Session, name: str, ats_type: str | None = None, ats_slug: str | None = None,
                          website: str | None = None) -> Company:
    key = normalize_company_name(name)
    company = db.scalar(select(Company).where(Company.normalized_name == key))
    if company is None:
        company = Company(name=name, normalized_name=key, ats_type=ats_type, ats_slug=ats_slug, website=website)
        db.add(company)
        db.commit()
    else:
        changed = False
        if ats_type and company.ats_type != ats_type:
            company.ats_type, changed = ats_type, True
        if ats_slug and company.ats_slug != ats_slug:
            company.ats_slug, changed = ats_slug, True
        if website and company.website != website:
            company.website, changed = website, True
        if changed:
            db.commit()
    return company
