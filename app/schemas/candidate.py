from pydantic import BaseModel, Field


class ExperienceEntry(BaseModel):
    company: str = ""
    title: str = ""
    location: str | None = None
    start_date: str | None = Field(default=None, description="As written in the resume, e.g. 'Jan 2021'")
    end_date: str | None = Field(default=None, description="As written, or 'Present'")
    bullets: list[str] = Field(default_factory=list)


class EducationEntry(BaseModel):
    institution: str = ""
    degree: str | None = None
    field_of_study: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    details: list[str] = Field(default_factory=list)


class ProjectEntry(BaseModel):
    name: str = ""
    description: str | None = None
    technologies: list[str] = Field(default_factory=list)
    bullets: list[str] = Field(default_factory=list)
    url: str | None = None


class CandidateProfile(BaseModel):
    """Structured representation of a resume. Every value must come from the resume text."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    summary: str | None = None
    skills: list[str] = Field(default_factory=list)
    experience: list[ExperienceEntry] = Field(default_factory=list)
    education: list[EducationEntry] = Field(default_factory=list)
    projects: list[ProjectEntry] = Field(default_factory=list)
    achievements: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)
    years_of_experience: float | None = None
    target_roles: list[str] = Field(default_factory=list, description="Roles the candidate appears to target")
    seniority: str | None = Field(default=None, description="junior | mid | senior | lead | executive")
