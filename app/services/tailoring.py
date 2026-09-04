"""Generate a job-specific resume from the original profile, then verify it against the original."""

import json

from sqlalchemy.orm import Session

from app.llm.base import LLMProvider
from app.llm.prompts import RESUME_TAILOR_SYSTEM
from app.models import Job, Resume, TailoredResume as TailoredResumeRow
from app.schemas.resume import TailoredResume
from app.services.analysis import get_analysis
from app.services.rendering import render_markdown
from app.services.resume_parser import get_profile
from app.services.verification import verify_tailored_resume


def build_tailor_prompt(resume: Resume, job: Job, analysis: dict | None) -> str:
    profile = get_profile(resume)
    return (
        f"ORIGINAL CANDIDATE PROFILE (the only source of truth):\n{profile.model_dump_json(indent=1)}\n\n"
        f"TARGET JOB:\nTitle: {job.title}\nCompany: {job.company_name}\nLocation: {job.location}\n"
        f"Structured summary: {json.dumps(job.summary) if job.summary else 'n/a'}\n"
        f"Description (excerpt):\n{(job.description or '')[:6000]}\n\n"
        f"MATCH ANALYSIS: {json.dumps(analysis) if analysis else 'n/a'}\n\n"
        "Produce the tailored resume now. Remember: reorder, select, and reword only."
    )


def tailor_resume(db: Session, llm: LLMProvider, resume: Resume, job: Job) -> TailoredResumeRow:
    analysis_row = get_analysis(db, resume.id, job.id)
    analysis = analysis_row.result if analysis_row else None
    tailored = llm.complete_structured(RESUME_TAILOR_SYSTEM, build_tailor_prompt(resume, job, analysis), TailoredResume)

    # Contact details are never for the LLM to change
    profile = get_profile(resume)
    tailored.full_name, tailored.email, tailored.phone = profile.full_name, profile.email, profile.phone
    tailored.location = tailored.location or profile.location

    verification = verify_tailored_resume(profile, resume.raw_text, tailored)
    row = TailoredResumeRow(
        resume_id=resume.id,
        job_id=job.id,
        content=tailored.model_dump(),
        markdown=render_markdown(tailored),
        verification_status=verification.status,
        verification_issues=[i.model_dump() for i in verification.issues],
        model=f"{llm.name}:{llm.chat_model}",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
