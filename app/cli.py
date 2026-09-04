"""Command-line runner for the pipeline, e.g.

  python -m app.cli parse-resume --user-email me@example.com --file resume.pdf
  python -m app.cli ingest --what "backend engineer" --where London
  python -m app.cli match --resume-id 1 --top-k 20
  python -m app.cli tailor --resume-id 1 --job-id 42
"""

import argparse
import json
from pathlib import Path

from sqlalchemy import select

from app.config import get_settings
from app.db.session import SessionLocal
from app.llm import get_llm
from app.models import Job, Resume, User
from app.schemas.job import JobFilters, JobQuery
from app.services.analysis import analyze_jobs
from app.services.ingestion import run_search_ingestion
from app.services.ranking import rank_jobs
from app.services.resume_parser import create_resume
from app.services.summarizer import summarize_and_embed_jobs
from app.services.tailoring import tailor_resume


def cmd_parse_resume(args):
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.user_email))
        if user is None:
            user = User(email=args.user_email, preferences={})
            db.add(user)
            db.commit()
        path = Path(args.file)
        resume = create_resume(db, get_llm(), user.id, path.name, path.read_bytes())
        print(f"resume_id={resume.id}")
        print(json.dumps(resume.profile, indent=1))


def cmd_ingest(args):
    with SessionLocal() as db:
        q = JobQuery(what=args.what, where=args.where, max_days_old=args.max_days_old, max_pages=args.max_pages)
        run = run_search_ingestion(db, get_settings(), args.source, q, refresh=args.refresh)
        print(f"run={run.id} status={run.status} fetched={run.fetched} inserted={run.inserted} "
              f"updated={run.updated} duplicates={run.duplicates} error={run.error}")


def cmd_match(args):
    with SessionLocal() as db:
        llm = get_llm()
        resume = db.get(Resume, args.resume_id)
        if resume is None:
            raise SystemExit("resume not found")
        n = summarize_and_embed_jobs(db, llm)
        print(f"summarised/embedded {n} jobs")
        filters = JobFilters(max_days_old=args.max_days_old, salary_min=args.salary_min,
                             location_contains=args.location, remote_only=args.remote_only)
        ranked = rank_jobs(db, resume, filters, args.top_k)
        print(f"shortlist: {len(ranked)}")
        if args.analyze:
            analyses = analyze_jobs(db, llm, resume, [j for j, _ in ranked])
            for (job, sim), a in sorted(zip(ranked, analyses), key=lambda x: x[1].match_score, reverse=True):
                print(f"[{a.match_score:5.1f}] sim={sim:.3f} #{job.id} {job.title} @ {job.company_name} "
                      f"({job.location}) missing={a.missing_skills}")
        else:
            for job, sim in ranked:
                print(f"sim={sim:.3f} #{job.id} {job.title} @ {job.company_name} ({job.location})")


def cmd_tailor(args):
    with SessionLocal() as db:
        resume = db.get(Resume, args.resume_id)
        job = db.get(Job, args.job_id)
        if resume is None or job is None:
            raise SystemExit("resume or job not found")
        row = tailor_resume(db, get_llm(), resume, job)
        print(f"tailored_resume_id={row.id} verification={row.verification_status}")
        for issue in row.verification_issues:
            print(f"  - [{issue['severity']}] {issue['section']}: {issue['message']}")
        print()
        print(row.markdown)


def main():
    p = argparse.ArgumentParser(prog="job-assistant")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("parse-resume")
    s.add_argument("--user-email", required=True)
    s.add_argument("--file", required=True)
    s.set_defaults(fn=cmd_parse_resume)

    s = sub.add_parser("ingest")
    s.add_argument("--source", default="adzuna")
    s.add_argument("--what", required=True)
    s.add_argument("--where")
    s.add_argument("--max-days-old", type=int, default=30)
    s.add_argument("--max-pages", type=int, default=3)
    s.add_argument("--refresh", action="store_true", help="bypass the API cache")
    s.set_defaults(fn=cmd_ingest)

    s = sub.add_parser("match")
    s.add_argument("--resume-id", type=int, required=True)
    s.add_argument("--top-k", type=int, default=get_settings().shortlist_size)
    s.add_argument("--max-days-old", type=int)
    s.add_argument("--salary-min", type=float)
    s.add_argument("--location")
    s.add_argument("--remote-only", action="store_true")
    s.add_argument("--analyze", action="store_true")
    s.set_defaults(fn=cmd_match)

    s = sub.add_parser("tailor")
    s.add_argument("--resume-id", type=int, required=True)
    s.add_argument("--job-id", type=int, required=True)
    s.set_defaults(fn=cmd_tailor)

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
