from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_resume_or_404, llm_dep, settings_dep
from app.api.serializers import analysis_out, job_out, tailored_out
from app.config import Settings
from app.db.session import get_db
from app.llm.base import LLMProvider
from app.models import Job, JobAnalysis, Resume
from app.schemas.api import (
    AnalysisOut, AnalyzeRequest, PipelineRequest, RankRequest, RankedJobOut, TailorRequest, TailoredResumeOut,
)
from app.services.analysis import analyze_jobs
from app.services.pipeline import run_pipeline
from app.services.ranking import rank_jobs
from app.services.summarizer import summarize_and_embed_jobs
from app.services.tailoring import tailor_resume

router = APIRouter(tags=["matching"])


def _resume(db: Session, resume_id: int) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(404, "Resume not found")
    if resume.profile_embedding is None:
        raise HTTPException(422, "Resume has no embedding")
    return resume


@router.post("/matches/rank", response_model=list[RankedJobOut])
def rank(body: RankRequest, db: Session = Depends(get_db), llm: LLMProvider = Depends(llm_dep),
         settings: Settings = Depends(settings_dep)):
    resume = _resume(db, body.resume_id)
    if body.summarize_missing:
        summarize_and_embed_jobs(db, llm)
    ranked = rank_jobs(db, resume, body.filters, body.top_k or settings.shortlist_size)
    return [RankedJobOut(job=job_out(j), similarity=s) for j, s in ranked]


@router.post("/matches/analyze", response_model=list[AnalysisOut])
def analyze(body: AnalyzeRequest, db: Session = Depends(get_db), llm: LLMProvider = Depends(llm_dep),
            settings: Settings = Depends(settings_dep)):
    resume = _resume(db, body.resume_id)
    sims: dict[int, float] = {}
    if body.job_ids:
        jobs = db.scalars(select(Job).where(Job.id.in_(body.job_ids))).all()
    else:
        summarize_and_embed_jobs(db, llm)
        ranked = rank_jobs(db, resume, body.filters, body.top_k or settings.shortlist_size)
        jobs = [j for j, _ in ranked]
        sims = {j.id: s for j, s in ranked}
    analyses = analyze_jobs(db, llm, resume, jobs)
    out = [analysis_out(j, a, sims.get(j.id)) for j, a in zip(jobs, analyses, strict=True)]
    return sorted(out, key=lambda x: x.analysis.match_score, reverse=True)


@router.get("/matches/{resume_id}", response_model=list[AnalysisOut])
def list_matches(resume_id: int, min_score: float = 0, limit: int = 50, db: Session = Depends(get_db)):
    rows = db.execute(
        select(JobAnalysis, Job)
        .join(Job, Job.id == JobAnalysis.job_id)
        .where(JobAnalysis.resume_id == resume_id, JobAnalysis.match_score >= min_score, Job.is_active.is_(True))
        .order_by(JobAnalysis.match_score.desc())
        .limit(limit)
    ).all()
    return [analysis_out(j, a) for a, j in rows]


@router.post("/tailor", response_model=TailoredResumeOut)
def tailor(body: TailorRequest, db: Session = Depends(get_db), llm: LLMProvider = Depends(llm_dep)):
    resume = db.get(Resume, body.resume_id)
    job = db.get(Job, body.job_id)
    if resume is None or job is None:
        raise HTTPException(404, "Resume or job not found")
    return tailored_out(tailor_resume(db, llm, resume, job))


@router.post("/pipeline/run")
def pipeline(body: PipelineRequest, db: Session = Depends(get_db), llm: LLMProvider = Depends(llm_dep),
             settings: Settings = Depends(settings_dep)):
    resume = _resume(db, body.resume_id)
    result = run_pipeline(db, llm, settings, resume, body.query, body.filters, body.sources, body.top_k, body.analyze)
    sims = {j.id: s for j, s in result.ranked}
    return {
        "ingestion_runs": [
            {"id": r.id, "source": r.source, "status": r.status, "fetched": r.fetched, "inserted": r.inserted,
             "updated": r.updated, "duplicates": r.duplicates, "error": r.error}
            for r in result.runs
        ],
        "summarized": result.summarized,
        "shortlist": [RankedJobOut(job=job_out(j), similarity=s) for j, s in result.ranked],
        "analyses": sorted(
            [analysis_out(db.get(Job, a.job_id), a, sims.get(a.job_id)) for a in result.analyses],
            key=lambda x: x.analysis.match_score, reverse=True,
        ),
    }
