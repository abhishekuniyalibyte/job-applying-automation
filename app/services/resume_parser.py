"""Resume upload -> text extraction (PyMuPDF) -> structured CandidateProfile -> embedding."""

from sqlalchemy.orm import Session

from app.llm.base import LLMProvider
from app.llm.prompts import RESUME_PARSER_SYSTEM
from app.models import Resume
from app.schemas.candidate import CandidateProfile
from app.services.text_builders import candidate_profile_text

MAX_RESUME_CHARS = 30_000


class ResumeParseError(ValueError):
    pass


def extract_text(filename: str | None, data: bytes) -> str:
    name = (filename or "").lower()
    if name.endswith(".pdf") or data[:5] == b"%PDF-":
        import pymupdf

        with pymupdf.open(stream=data, filetype="pdf") as doc:
            text = "\n".join(page.get_text("text") for page in doc)
    elif name.endswith((".txt", ".md")) or not name:
        text = data.decode("utf-8", errors="replace")
    else:
        raise ResumeParseError("Unsupported file type; upload a PDF, TXT, or Markdown resume")
    text = text.replace("\x00", "").strip()
    if len(text) < 50:
        raise ResumeParseError("Could not extract meaningful text from the resume")
    return text[:MAX_RESUME_CHARS]


def parse_resume_text(llm: LLMProvider, raw_text: str) -> CandidateProfile:
    return llm.complete_structured(RESUME_PARSER_SYSTEM, f"RESUME TEXT:\n\n{raw_text}", CandidateProfile)


def create_resume(db: Session, llm: LLMProvider, user_id: int, filename: str | None, data: bytes) -> Resume:
    raw_text = extract_text(filename, data)
    profile = parse_resume_text(llm, raw_text)
    profile_text = candidate_profile_text(profile)
    embedding = llm.embed([profile_text])[0]
    resume = Resume(
        user_id=user_id,
        filename=filename,
        raw_text=raw_text,
        profile=profile.model_dump(),
        profile_text=profile_text,
        profile_embedding=embedding,
        parser_model=f"{llm.name}:{llm.chat_model}",
    )
    db.add(resume)
    db.commit()
    db.refresh(resume)
    return resume


def get_profile(resume: Resume) -> CandidateProfile:
    return CandidateProfile.model_validate(resume.profile or {})
