from pydantic import BaseModel, Field

from app.schemas.candidate import EducationEntry, ExperienceEntry, ProjectEntry


class TailoredResume(BaseModel):
    """A re-ordered / re-worded subset of the original CandidateProfile. Nothing new may be introduced."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = Field(default=None, description="Rewritten summary using only facts from the original")
    skills: list[str] = Field(default_factory=list, description="Subset of original skills, most relevant first")
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    tailoring_notes: list[str] = Field(default_factory=list, description="What was emphasised and why")


class VerificationIssue(BaseModel):
    severity: str  # error | warning
    section: str
    message: str


class VerificationResult(BaseModel):
    status: str  # verified | flagged | rejected
    issues: list[VerificationIssue] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status != "rejected"
