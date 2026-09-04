from fastapi import FastAPI

from app.api.routes import companies, jobs, matches, resumes, users
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description=(
        "AI-powered job search and resume tailoring. Pipeline: resume upload -> Adzuna/ATS ingestion -> "
        "normalisation & dedup -> filtering -> pgvector ranking -> LLM analysis -> tailored resume -> "
        "fabrication verification. Final application is always submitted by the user."
    ),
)

app.include_router(users.router)
app.include_router(resumes.router)
app.include_router(companies.router)
app.include_router(jobs.router)
app.include_router(matches.router)


@app.get("/health", tags=["meta"])
def health():
    return {"status": "ok", "llm_provider": settings.llm_provider, "embedding_dim": settings.embedding_dim}
