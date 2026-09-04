from datetime import datetime

from pydantic import BaseModel, Field


class JobQuery(BaseModel):
    what: str = Field(description="Role / keywords, e.g. 'backend engineer'")
    where: str | None = Field(default=None, description="Location, e.g. 'London'")
    max_days_old: int | None = 30
    salary_min: float | None = None
    results_per_page: int = 50
    max_pages: int = 3
    full_time: bool | None = None


class NormalizedJob(BaseModel):
    """Common schema every job source maps into."""

    source: str
    source_job_id: str
    title: str
    company_name: str | None = None
    location: str | None = None
    description: str = ""
    salary_min: float | None = None
    salary_max: float | None = None
    salary_currency: str | None = None
    remote: bool | None = None
    employment_type: str | None = None
    posted_at: datetime | None = None
    source_url: str | None = None
    apply_url: str | None = None
    apply_url_verified: bool = False
    raw: dict = Field(default_factory=dict)


class JobSummary(BaseModel):
    """Concise structured summary of a job; this (not the full description) is embedded."""

    role_title: str = ""
    seniority: str | None = Field(default=None, description="junior | mid | senior | lead | executive")
    required_skills: list[str] = Field(default_factory=list)
    nice_to_have_skills: list[str] = Field(default_factory=list)
    domain: str | None = None
    years_experience_min: float | None = None
    remote_policy: str | None = Field(default=None, description="remote | hybrid | onsite | unknown")
    one_line: str = Field(default="", description="One sentence describing the role")


class JobFilters(BaseModel):
    max_days_old: int | None = None
    salary_min: float | None = None
    require_salary: bool = False  # jobs without salary stay eligible unless True
    location_contains: str | None = None
    remote_only: bool = False
    exclude_title_keywords: list[str] = Field(default_factory=list)
    include_title_keywords: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
