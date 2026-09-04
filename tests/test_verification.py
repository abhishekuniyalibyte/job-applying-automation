from app.schemas.candidate import CandidateProfile, EducationEntry, ExperienceEntry, ProjectEntry
from app.schemas.resume import TailoredResume
from app.services.verification import verify_tailored_resume

RAW = """Jane Doe - jane@example.com - London
Senior Backend Engineer, Acme Ltd, Jan 2021 - Present
- Built FastAPI services handling 2M requests/day on PostgreSQL
- Led migration to Kubernetes, cutting deploy time by 40%
Backend Engineer, Beta Inc, 2018 - 2020
- Maintained Django monolith and Celery workers
Education: BSc Computer Science, University of Leeds, 2014 - 2018
Skills: Python, FastAPI, PostgreSQL, Docker, Kubernetes, Django, Celery, Redis
Projects: JobRadar - a job aggregator built with Python and pgvector
"""

ORIGINAL = CandidateProfile(
    full_name="Jane Doe", email="jane@example.com", location="London",
    skills=["Python", "FastAPI", "PostgreSQL", "Docker", "Kubernetes", "Django", "Celery", "Redis"],
    experience=[
        ExperienceEntry(company="Acme Ltd", title="Senior Backend Engineer", start_date="Jan 2021", end_date="Present",
                        bullets=["Built FastAPI services handling 2M requests/day on PostgreSQL",
                                 "Led migration to Kubernetes, cutting deploy time by 40%"]),
        ExperienceEntry(company="Beta Inc", title="Backend Engineer", start_date="2018", end_date="2020",
                        bullets=["Maintained Django monolith and Celery workers"]),
    ],
    education=[EducationEntry(institution="University of Leeds", degree="BSc", field_of_study="Computer Science",
                              start_date="2014", end_date="2018")],
    projects=[ProjectEntry(name="JobRadar", description="a job aggregator built with Python and pgvector",
                           technologies=["Python", "pgvector"])],
)


def _faithful() -> TailoredResume:
    return TailoredResume(
        full_name="Jane Doe", email="jane@example.com", location="London",
        summary="Backend engineer focused on Python services and PostgreSQL.",
        skills=["Python", "FastAPI", "PostgreSQL", "Kubernetes"],
        experience=[
            ExperienceEntry(company="Acme Ltd", title="Senior Backend Engineer", start_date="Jan 2021", end_date="Present",
                            bullets=["Built FastAPI services on PostgreSQL handling 2M requests/day",
                                     "Led Kubernetes migration, cutting deploy time by 40%"]),
        ],
        education=ORIGINAL.education,
        projects=[ProjectEntry(name="JobRadar", technologies=["Python", "pgvector"],
                               description="a job aggregator built with Python and pgvector")],
    )


def test_faithful_tailoring_is_verified():
    result = verify_tailored_resume(ORIGINAL, RAW, _faithful())
    assert result.status == "verified", result.issues


def test_new_employer_is_rejected():
    t = _faithful()
    t.experience.append(ExperienceEntry(company="Google", title="Staff Engineer", start_date="2015", end_date="2016"))
    result = verify_tailored_resume(ORIGINAL, RAW, t)
    assert result.status == "rejected"
    assert any("Google" in i.message for i in result.issues if i.severity == "error")


def test_new_skill_is_rejected():
    t = _faithful()
    t.skills.append("Rust")
    result = verify_tailored_resume(ORIGINAL, RAW, t)
    assert result.status == "rejected"
    assert any("Rust" in i.message for i in result.issues)


def test_changed_dates_are_rejected():
    t = _faithful()
    t.experience[0].start_date = "Jan 2019"
    result = verify_tailored_resume(ORIGINAL, RAW, t)
    assert result.status == "rejected"


def test_invented_metric_is_rejected():
    t = _faithful()
    t.experience[0].bullets[0] = "Built FastAPI services on PostgreSQL handling 10M requests/day"
    result = verify_tailored_resume(ORIGINAL, RAW, t)
    assert result.status == "rejected"
    assert any("10" in i.message for i in result.issues)


def test_new_degree_is_rejected():
    t = _faithful()
    t.education[0] = EducationEntry(institution="University of Leeds", degree="PhD", field_of_study="Computer Science",
                                    start_date="2014", end_date="2018")
    assert verify_tailored_resume(ORIGINAL, RAW, t).status == "rejected"


def test_unrelated_bullet_is_flagged_not_rejected():
    t = _faithful()
    t.experience[0].bullets.append("Mentored the whole organisation on leadership excellence")
    result = verify_tailored_resume(ORIGINAL, RAW, t)
    assert result.status == "flagged"
    assert all(i.severity == "warning" for i in result.issues)


def test_new_project_is_rejected():
    t = _faithful()
    t.projects.append(ProjectEntry(name="SkyNet", technologies=["Python"]))
    assert verify_tailored_resume(ORIGINAL, RAW, t).status == "rejected"
