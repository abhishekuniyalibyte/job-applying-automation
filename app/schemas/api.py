from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.analysis import JobMatchAnalysis
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobFilters, JobQuery
from app.schemas.resume import TailoredResume, VerificationIssue


class UserCreate(BaseModel):
    email: str
    preferences: dict = Field(default_factory=dict)


class UserOut(BaseModel):
    id: int
    email: str
    preferences: dict


class ResumeOut(BaseModel):
    id: int
    user_id: int
    filename: str | None
    profile: CandidateProfile | None
    has_embedding: bool
    created_at: datetime


class CompanyCreate(BaseModel):
    name: str
    ats_type: str | None = None  # greenhouse | lever
    ats_slug: str | None = None
    website: str | None = None


class CompanyOut(BaseModel):
    id: int
    name: str
    ats_type: str | None
    ats_slug: str | None
    website: str | None


class IngestRequest(BaseModel):
    query: JobQuery
    source: str = "adzuna"
    refresh: bool = False  # bypass the API cache and fetch live


class IngestionRunOut(BaseModel):
    id: int
    source: str
    status: str
    fetched: int
    inserted: int
    updated: int
    duplicates: int
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class JobOut(BaseModel):
    id: int
    source: str
    source_job_id: str
    title: str
    company_name: str | None
    location: str | None
    salary_min: float | None
    salary_max: float | None
    salary_currency: str | None
    remote: bool | None
    posted_at: datetime | None
    last_seen_at: datetime
    is_active: bool
    source_url: str | None
    apply_url: str | None
    apply_url_verified: bool
    duplicate_of_id: int | None
    summary: dict | None


class RankRequest(BaseModel):
    resume_id: int
    filters: JobFilters = Field(default_factory=JobFilters)
    top_k: int | None = None
    summarize_missing: bool = True  # summarise + embed jobs that lack an embedding before ranking


class RankedJobOut(BaseModel):
    job: JobOut
    similarity: float


class AnalyzeRequest(BaseModel):
    resume_id: int
    job_ids: list[int] | None = None  # if omitted, rank first and analyse the shortlist
    filters: JobFilters = Field(default_factory=JobFilters)
    top_k: int | None = None


class AnalysisOut(BaseModel):
    job: JobOut
    analysis: JobMatchAnalysis
    similarity: float | None = None


class TailorRequest(BaseModel):
    resume_id: int
    job_id: int


class TailoredResumeOut(BaseModel):
    id: int
    resume_id: int
    job_id: int
    content: TailoredResume
    markdown: str
    verification_status: str
    verification_issues: list[VerificationIssue]
    created_at: datetime


class JobDetailOut(BaseModel):
    job: JobOut
    description: str
    analysis: JobMatchAnalysis | None
    tailored_resume: TailoredResumeOut | None
    application: dict  # {"apply_url": ..., "apply_url_verified": ..., "source_url": ...}


class PipelineRequest(BaseModel):
    resume_id: int
    query: JobQuery
    filters: JobFilters = Field(default_factory=JobFilters)
    sources: list[str] = Field(default_factory=lambda: ["adzuna"])
    top_k: int | None = None
    analyze: bool = True
