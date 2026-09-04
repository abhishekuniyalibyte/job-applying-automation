from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db.session import get_db
from app.llm import get_llm
from app.llm.base import LLMProvider
from app.models import Job, Resume


def llm_dep() -> LLMProvider:
    try:
        return get_llm()
    except RuntimeError as err:
        raise HTTPException(status_code=503, detail=str(err)) from err


def settings_dep() -> Settings:
    return get_settings()


def get_resume_or_404(resume_id: int, db: Session = Depends(get_db)) -> Resume:
    resume = db.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return resume


def get_job_or_404(job_id: int, db: Session = Depends(get_db)) -> Job:
    job = db.get(Job, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job
