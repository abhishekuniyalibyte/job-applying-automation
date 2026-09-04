from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_resume_or_404, llm_dep
from app.api.serializers import resume_out
from app.db.session import get_db
from app.llm.base import LLMProvider
from app.models import Resume, User
from app.schemas.api import ResumeOut
from app.services.resume_parser import ResumeParseError, create_resume

router = APIRouter(prefix="/resumes", tags=["resumes"])


@router.post("/upload", response_model=ResumeOut)
async def upload_resume(
    user_id: int = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    llm: LLMProvider = Depends(llm_dep),
):
    if db.get(User, user_id) is None:
        raise HTTPException(404, "User not found")
    data = await file.read()
    try:
        resume = create_resume(db, llm, user_id, file.filename, data)
    except ResumeParseError as err:
        raise HTTPException(422, str(err)) from err
    return resume_out(resume)


@router.get("/{resume_id}", response_model=ResumeOut)
def get_resume(resume: Resume = Depends(get_resume_or_404)):
    return resume_out(resume)


@router.get("", response_model=list[ResumeOut])
def list_resumes(user_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(Resume).where(Resume.user_id == user_id).order_by(Resume.created_at.desc())).all()
    return [resume_out(r) for r in rows]
