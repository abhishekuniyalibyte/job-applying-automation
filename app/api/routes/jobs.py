from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_job_or_404, llm_dep, settings_dep
from app.api.serializers import application_block, job_out, tailored_out
from app.config import Settings
from app.db.session import get_db
from app.llm.base import LLMProvider
from app.models import IngestionRun, Job, TailoredResume
from app.schemas.api import IngestRequest, IngestionRunOut, JobDetailOut, JobOut
from app.schemas.analysis import JobMatchAnalysis
from app.services.analysis import get_analysis
from app.services.ingestion import run_search_ingestion
from app.services.summarizer import summarize_and_embed_jobs

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.post("/ingest", response_model=IngestionRunOut)
def ingest_jobs(body: IngestRequest, db: Session = Depends(get_db), settings: Settings = Depends(settings_dep)):
    run = run_search_ingestion(db, settings, body.source, body.query, refresh=body.refresh)
    return IngestionRunOut.model_validate(run, from_attributes=True)


@router.post("/summarize")
def summarize_jobs(limit: int | None = None, db: Session = Depends(get_db), llm: LLMProvider = Depends(llm_dep)):
    """Summarise + embed jobs that do not yet have an embedding (cached afterwards)."""
    return {"processed": summarize_and_embed_jobs(db, llm, limit=limit)}


@router.get("/runs", response_model=list[IngestionRunOut])
def list_runs(limit: int = 20, db: Session = Depends(get_db)):
    rows = db.scalars(select(IngestionRun).order_by(IngestionRun.started_at.desc()).limit(limit)).all()
    return [IngestionRunOut.model_validate(r, from_attributes=True) for r in rows]


@router.get("", response_model=list[JobOut])
def list_jobs(
    active_only: bool = True,
    include_duplicates: bool = False,
    source: str | None = None,
    q: str | None = Query(default=None, description="Title substring"),
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    stmt = select(Job)
    if active_only:
        stmt = stmt.where(Job.is_active.is_(True))
    if not include_duplicates:
        stmt = stmt.where(Job.duplicate_of_id.is_(None))
    if source:
        stmt = stmt.where(Job.source == source)
    if q:
        stmt = stmt.where(Job.title.ilike(f"%{q}%"))
    stmt = stmt.order_by(Job.posted_at.desc().nullslast(), Job.id.desc()).offset(offset).limit(limit)
    return [job_out(j) for j in db.scalars(stmt).all()]


@router.get("/{job_id}", response_model=JobDetailOut)
def job_detail(
    job: Job = Depends(get_job_or_404),
    resume_id: int | None = None,
    db: Session = Depends(get_db),
):
    """Job details + (if resume_id given) match analysis, skill gaps, latest tailored resume, and apply link."""
    analysis = None
    tailored = None
    if resume_id is not None:
        a = get_analysis(db, resume_id, job.id)
        analysis = JobMatchAnalysis.model_validate(a.result) if a else None
        t = db.scalar(
            select(TailoredResume)
            .where(TailoredResume.resume_id == resume_id, TailoredResume.job_id == job.id)
            .order_by(TailoredResume.created_at.desc())
        )
        tailored = tailored_out(t) if t else None
    return JobDetailOut(
        job=job_out(job),
        description=job.description,
        analysis=analysis,
        tailored_resume=tailored,
        application=application_block(job),
    )
