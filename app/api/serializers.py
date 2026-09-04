from app.models import Job, JobAnalysis, Resume, TailoredResume
from app.schemas.analysis import JobMatchAnalysis
from app.schemas.api import AnalysisOut, JobOut, ResumeOut, TailoredResumeOut
from app.schemas.candidate import CandidateProfile
from app.schemas.resume import TailoredResume as TailoredResumeSchema, VerificationIssue


def job_out(job: Job) -> JobOut:
    return JobOut(
        id=job.id, source=job.source, source_job_id=job.source_job_id, title=job.title,
        company_name=job.company_name, location=job.location, salary_min=job.salary_min,
        salary_max=job.salary_max, salary_currency=job.salary_currency, remote=job.remote,
        posted_at=job.posted_at, last_seen_at=job.last_seen_at, is_active=job.is_active,
        source_url=job.source_url, apply_url=job.apply_url, apply_url_verified=job.apply_url_verified,
        duplicate_of_id=job.duplicate_of_id, summary=job.summary,
    )


def resume_out(r: Resume) -> ResumeOut:
    return ResumeOut(
        id=r.id, user_id=r.user_id, filename=r.filename,
        profile=CandidateProfile.model_validate(r.profile) if r.profile else None,
        has_embedding=r.profile_embedding is not None, created_at=r.created_at,
    )


def analysis_out(job: Job, a: JobAnalysis, similarity: float | None = None) -> AnalysisOut:
    return AnalysisOut(job=job_out(job), analysis=JobMatchAnalysis.model_validate(a.result), similarity=similarity)


def tailored_out(t: TailoredResume) -> TailoredResumeOut:
    return TailoredResumeOut(
        id=t.id, resume_id=t.resume_id, job_id=t.job_id,
        content=TailoredResumeSchema.model_validate(t.content), markdown=t.markdown,
        verification_status=t.verification_status,
        verification_issues=[VerificationIssue.model_validate(i) for i in t.verification_issues],
        created_at=t.created_at,
    )


def application_block(job: Job) -> dict:
    """Never present an aggregator redirect as a direct employer link."""
    return {
        "apply_url": job.apply_url if job.apply_url_verified else None,
        "apply_url_verified": job.apply_url_verified,
        "source_url": job.source_url,
        "note": (
            "Verified employer/ATS application link."
            if job.apply_url_verified
            else "Only an aggregator redirect is available; it may lead to a third-party listing."
        ),
    }
