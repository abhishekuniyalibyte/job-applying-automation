from app.llm.fake_provider import FakeProvider
from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobSummary
from app.services.text_builders import candidate_profile_text, job_summary_text


def _cos(a, b):
    return sum(x * y for x, y in zip(a, b))


def test_fake_embeddings_rank_similar_text_closer():
    llm = FakeProvider(embedding_dim=128)
    profile = CandidateProfile(skills=["Python", "FastAPI", "PostgreSQL"], target_roles=["Backend Engineer"])
    backend = JobSummary(role_title="Backend Engineer", required_skills=["Python", "FastAPI", "PostgreSQL"])
    sales = JobSummary(role_title="Sales Manager", required_skills=["Negotiation", "CRM"])
    p, b, s = llm.embed([candidate_profile_text(profile), job_summary_text(backend), job_summary_text(sales)])
    assert len(p) == 128
    assert _cos(p, b) > _cos(p, s)


def test_fake_structured_returns_defaults_or_handler():
    llm = FakeProvider(handlers={JobSummary: lambda sys, usr: JobSummary(role_title="X")})
    assert llm.complete_structured("s", "u", JobSummary).role_title == "X"
    assert llm.complete_structured("s", "u", CandidateProfile).skills == []
