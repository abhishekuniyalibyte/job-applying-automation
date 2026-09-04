"""End-to-end orchestration: ingest -> summarise/embed -> filter+rank -> LLM analyse."""

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.config import Settings
from app.llm.base import LLMProvider
from app.models import IngestionRun, Job, JobAnalysis, Resume
from app.schemas.job import JobFilters, JobQuery
from app.services.analysis import analyze_jobs
from app.services.ingestion import run_search_ingestion
from app.services.ranking import rank_jobs
from app.services.summarizer import summarize_and_embed_jobs


@dataclass
class PipelineResult:
    runs: list[IngestionRun] = field(default_factory=list)
    summarized: int = 0
    ranked: list[tuple[Job, float]] = field(default_factory=list)
    analyses: list[JobAnalysis] = field(default_factory=list)


def run_pipeline(
    db: Session,
    llm: LLMProvider,
    settings: Settings,
    resume: Resume,
    query: JobQuery,
    filters: JobFilters,
    sources: list[str] | None = None,
    top_k: int | None = None,
    analyze: bool = True,
) -> PipelineResult:
    result = PipelineResult()
    top_k = top_k or settings.shortlist_size
    for name in sources or ["adzuna"]:
        result.runs.append(run_search_ingestion(db, settings, name, query))
    result.summarized = summarize_and_embed_jobs(db, llm)
    result.ranked = rank_jobs(db, resume, filters, top_k)
    if analyze:
        result.analyses = analyze_jobs(db, llm, resume, [job for job, _ in result.ranked])
    return result
