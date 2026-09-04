"""Compact textual representations that get embedded (never the full description)."""

from app.schemas.candidate import CandidateProfile
from app.schemas.job import JobSummary


def candidate_profile_text(p: CandidateProfile) -> str:
    recent_titles = [e.title for e in p.experience[:3] if e.title]
    parts = [
        f"Target roles: {', '.join(p.target_roles) or ', '.join(recent_titles) or 'unspecified'}.",
        f"Seniority: {p.seniority or 'unknown'}.",
        f"Years of experience: {p.years_of_experience if p.years_of_experience is not None else 'unknown'}.",
        f"Skills: {', '.join(p.skills)}.",
        f"Recent titles: {', '.join(recent_titles)}.",
    ]
    if p.summary:
        parts.append(f"Summary: {p.summary}")
    if p.location:
        parts.append(f"Location: {p.location}.")
    return " ".join(parts)


def job_summary_text(s: JobSummary) -> str:
    parts = [
        f"Role: {s.role_title}.",
        f"Seniority: {s.seniority or 'unknown'}.",
        f"Required skills: {', '.join(s.required_skills)}.",
    ]
    if s.nice_to_have_skills:
        parts.append(f"Nice to have: {', '.join(s.nice_to_have_skills)}.")
    if s.domain:
        parts.append(f"Domain: {s.domain}.")
    if s.years_experience_min is not None:
        parts.append(f"Minimum experience: {s.years_experience_min} years.")
    if s.remote_policy:
        parts.append(f"Remote policy: {s.remote_policy}.")
    if s.one_line:
        parts.append(s.one_line)
    return " ".join(parts)
