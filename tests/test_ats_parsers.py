from app.services.job_sources.greenhouse import html_to_text, parse_greenhouse_job
from app.services.job_sources.lever import parse_lever_posting


def test_greenhouse_gives_verified_apply_url():
    j = {"id": 123, "title": "Platform Engineer", "absolute_url": "https://boards.greenhouse.io/acme/jobs/123",
         "location": {"name": "Remote - UK"}, "content": "<p>We need &lt;3 for <b>Kubernetes</b>.</p><ul><li>Go</li></ul>",
         "updated_at": "2026-08-20T09:00:00-04:00", "departments": [{"name": "Infra"}]}
    job = parse_greenhouse_job(j, "Acme")
    assert job.source == "greenhouse" and job.source_job_id == "123"
    assert job.apply_url == job.source_url and job.apply_url_verified is True
    assert job.remote is True
    assert "Kubernetes" in job.description and "<b>" not in job.description
    assert job.posted_at is not None


def test_html_to_text_handles_entities_and_blocks():
    assert html_to_text("<p>a &amp; b</p><p>c</p>") == "a & b\nc"


def test_lever_posting_maps_fields():
    p = {"id": "abc-1", "text": "Backend Engineer", "hostedUrl": "https://jobs.lever.co/acme/abc-1",
         "applyUrl": "https://jobs.lever.co/acme/abc-1/apply", "createdAt": 1756000000000,
         "categories": {"location": "London", "commitment": "Full-time", "team": "Eng"},
         "workplaceType": "hybrid", "descriptionPlain": "Build APIs.",
         "lists": [{"text": "Requirements", "content": "Python"}]}
    job = parse_lever_posting(p, "Acme")
    assert job.source == "lever"
    assert job.apply_url.endswith("/apply") and job.apply_url_verified
    assert job.employment_type == "Full-time"
    assert job.remote is None
    assert "Requirements" in job.description and "Python" in job.description
