from pydantic import BaseModel, Field


class JobMatchAnalysis(BaseModel):
    match_score: float = Field(default=0, ge=0, le=100)
    matched_skills: list[str] = Field(default_factory=list)
    missing_skills: list[str] = Field(default_factory=list)
    experience_compatibility: str = Field(default="unknown", description="strong | adequate | under | over | unknown")
    experience_explanation: str = ""
    location_compatibility: str = Field(default="unknown", description="match | remote_ok | relocation | mismatch | unknown")
    location_explanation: str = ""
    explanation: str = Field(default="", description="Why this score")
    recommendations: list[str] = Field(default_factory=list, description="What the candidate could emphasise or learn")
