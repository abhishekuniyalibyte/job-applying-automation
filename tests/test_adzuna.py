import json
from datetime import UTC, datetime
from pathlib import Path

from app.services.job_sources.adzuna import parse_adzuna_result

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "adzuna_page.json").read_text())


def test_parse_adzuna_result_maps_fields():
    job = parse_adzuna_result(FIXTURE["results"][0], country="gb")
    assert job.source == "adzuna"
    assert job.source_job_id == "4567890123"
    assert job.company_name == "Acme Ltd"
    assert job.location == "London, UK"
    assert job.salary_min == 70000 and job.salary_max == 90000
    assert job.salary_currency == "GBP"
    assert job.posted_at == datetime(2026, 8, 30, 10, 15, tzinfo=UTC)
    assert job.remote is True
    assert job.employment_type == "full_time"
    # Adzuna redirect is stored as source_url, never as a verified apply link
    assert job.source_url.startswith("https://www.adzuna.co.uk/")
    assert job.apply_url is None
    assert job.apply_url_verified is False


def test_parse_adzuna_result_missing_salary_stays_eligible():
    job = parse_adzuna_result(FIXTURE["results"][1], country="gb")
    assert job.salary_min is None and job.salary_max is None and job.salary_currency is None
    assert job.remote is None
