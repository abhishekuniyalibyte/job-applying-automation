from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.schemas.job import JobFilters
from app.services.filtering import job_passes_filters

NOW = datetime(2026, 9, 4, tzinfo=UTC)


@dataclass
class J:
    title: str = "Backend Engineer"
    source: str = "adzuna"
    location: str | None = "London, UK"
    remote: bool | None = None
    salary_min: float | None = None
    salary_max: float | None = None
    posted_at: datetime | None = NOW - timedelta(days=3)
    first_seen_at: datetime = NOW
    is_active: bool = True
    duplicate_of_id: int | None = None


def test_no_filters_passes_active_non_duplicate():
    assert job_passes_filters(J(), JobFilters(), NOW)
    assert not job_passes_filters(J(is_active=False), JobFilters(), NOW)
    assert not job_passes_filters(J(duplicate_of_id=7), JobFilters(), NOW)


def test_posting_date_filter_uses_first_seen_when_unknown():
    f = JobFilters(max_days_old=7)
    assert job_passes_filters(J(posted_at=NOW - timedelta(days=10)), f, NOW) is False
    assert job_passes_filters(J(posted_at=None, first_seen_at=NOW - timedelta(days=1)), f, NOW) is True


def test_missing_salary_remains_eligible_unless_required():
    f = JobFilters(salary_min=60000)
    assert job_passes_filters(J(), f, NOW) is True
    assert job_passes_filters(J(salary_max=50000), f, NOW) is False
    assert job_passes_filters(J(salary_min=65000), f, NOW) is True
    assert job_passes_filters(J(), JobFilters(salary_min=60000, require_salary=True), NOW) is False


def test_location_and_remote():
    f = JobFilters(location_contains="london")
    assert job_passes_filters(J(location="Central London"), f, NOW)
    assert not job_passes_filters(J(location="Leeds"), f, NOW)
    assert job_passes_filters(J(location="Leeds", remote=True), f, NOW)
    assert not job_passes_filters(J(), JobFilters(remote_only=True), NOW)


def test_title_keywords_and_sources():
    assert not job_passes_filters(J(title="Senior Backend Engineer"), JobFilters(exclude_title_keywords=["senior"]), NOW)
    assert not job_passes_filters(J(title="Sales Lead"), JobFilters(include_title_keywords=["engineer"]), NOW)
    assert not job_passes_filters(J(source="lever"), JobFilters(sources=["adzuna"]), NOW)
