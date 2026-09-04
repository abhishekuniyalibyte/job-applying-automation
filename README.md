# Job Assistant — AI job search & resume tailoring (MVP)

Finds and ranks job opportunities against a candidate's resume, explains each match, and generates a
job-specific resume that is **verified against the original** so nothing is fabricated. The user always
submits the final application themselves.

## Pipeline

```
resume upload ─▶ PyMuPDF text ─▶ LLM → CandidateProfile ─▶ embedding (pgvector)
                                                                  │
Adzuna / Greenhouse / Lever ─▶ NormalizedJob ─▶ upsert (source, source_job_id)
        │                                          ├─ dedupe (normalised URL, company|title|location)
        │                                          └─ freshness (posted_at, first/last_seen_at, last_verified_at)
        ▼
local filters (date, salary, location, remote, keywords)
        ▼
LLM JobSummary per job (cached) ─▶ embedding (cached) ─▶ cosine shortlist (top-K)
        ▼
LLM JobMatchAnalysis per (resume, job) (cached): score, matched/missing skills, experience & location fit
        ▼
LLM TailoredResume (reorder / select / reword only) ─▶ verification vs original ─▶ verified | flagged | rejected
        ▼
UI: job, analysis, gaps, tailored resume, apply link (verified ATS link vs aggregator redirect kept separate)
```

Every stage caches in PostgreSQL (`api_cache`, `jobs.summary*`, `job_analyses`) so a job never pays
for the same API/LLM call twice. Redis/Celery are intentionally deferred.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2 · PostgreSQL 16 + pgvector · Pydantic v2 · Alembic · Docker · PyMuPDF ·
OpenAI or Gemini behind `app/llm/` (plus an offline `fake` provider for tests/dev).

## Quick start

```bash
cp .env.example .env            # add ADZUNA_APP_ID/KEY and OPENAI_API_KEY (or GEMINI_API_KEY)
docker compose up -d db         # pgvector-enabled Postgres on :5432
make install                    # venv + requirements
make migrate                    # alembic upgrade head
make run                        # http://localhost:8000/docs
```

Or everything in Docker: `docker compose up --build`.

### Embedding dimension

`EMBEDDING_DIM` (default 768) sizes the pgvector columns in the initial migration and is passed to the
embedding API (`dimensions` for OpenAI, `output_dimensionality` for Gemini) so both fit. Change it **before**
the first `alembic upgrade`; changing it later needs a new migration that alters the vector columns.

## API walk-through

```bash
# 1. user
curl -sX POST localhost:8000/users -H 'content-type: application/json' \
  -d '{"email":"jane@example.com","preferences":{"role":"backend engineer","location":"London"}}'

# 2. resume upload -> parsed CandidateProfile + embedding
curl -sX POST localhost:8000/resumes/upload -F user_id=1 -F file=@resume.pdf

# 3. ingest from Adzuna (idempotent; re-running refreshes last_seen_at)
curl -sX POST localhost:8000/jobs/ingest -H 'content-type: application/json' \
  -d '{"source":"adzuna","query":{"what":"backend engineer","where":"London","max_days_old":30,"max_pages":3}}'

# 4. shortlist by semantic similarity (summarises/embeds new jobs first)
curl -sX POST localhost:8000/matches/rank -H 'content-type: application/json' \
  -d '{"resume_id":1,"filters":{"max_days_old":30,"salary_min":60000},"top_k":25}'

# 5. LLM analysis of the shortlist (or explicit job_ids)
curl -sX POST localhost:8000/matches/analyze -H 'content-type: application/json' -d '{"resume_id":1}'

# 6. tailored resume for one job + fabrication verification
curl -sX POST localhost:8000/tailor -H 'content-type: application/json' -d '{"resume_id":1,"job_id":42}'

# 7. everything the UI needs for one job
curl -s 'localhost:8000/jobs/42?resume_id=1'

# One-shot: ingest -> summarise -> rank -> analyse
curl -sX POST localhost:8000/pipeline/run -H 'content-type: application/json' \
  -d '{"resume_id":1,"query":{"what":"backend engineer","where":"London"},"top_k":20}'
```

### ATS boards (Greenhouse / Lever)

```bash
curl -sX POST localhost:8000/companies -H 'content-type: application/json' \
  -d '{"name":"Acme","ats_type":"greenhouse","ats_slug":"acme"}'
curl -sX POST localhost:8000/companies/1/ingest
```

ATS jobs carry a **verified** `apply_url`; Adzuna jobs only carry `source_url` (redirect). A full board fetch
marks postings that disappeared as inactive. Responses are cached for `API_CACHE_TTL_HOURS`; pass
`?refresh=true` (or `"refresh": true` on `/jobs/ingest`) to bypass the cache and re-verify now.

### CLI

```bash
.venv/bin/python -m app.cli parse-resume --user-email jane@example.com --file resume.pdf
.venv/bin/python -m app.cli ingest --what "backend engineer" --where London
.venv/bin/python -m app.cli match --resume-id 1 --top-k 20 --analyze
.venv/bin/python -m app.cli tailor --resume-id 1 --job-id 42
```

## Fabrication guard (`app/services/verification.py`)

The tailoring prompt only allows reordering, selecting, and rewording. The verifier then checks the output
against the original structured profile **and** the raw resume text:

| Check | Result |
|---|---|
| New employer / title / date / location on an experience entry | rejected |
| New institution / degree / field / date | rejected |
| Skill or technology not in the original | rejected |
| Project not in the original | rejected |
| Number/metric that never appeared in the original entry or resume | rejected |
| Certification not in the original | rejected |
| Bullet / achievement sharing < 50–60 % of its wording with the original | flagged |

Contact details are copied straight from the original and never left to the LLM.

## Layout

```
app/
  config.py            settings (.env)
  main.py              FastAPI app
  cli.py               command-line runner
  db/                  engine/session, declarative base
  models/              users, resumes, companies, jobs, job_analyses, tailored_resumes, ingestion_runs, api_cache
  schemas/             CandidateProfile, NormalizedJob, JobSummary, JobMatchAnalysis, TailoredResume, API DTOs
  llm/                 provider abstraction: openai, gemini, fake + prompts
  services/
    job_sources/       adzuna, greenhouse, lever (+ registry, cached HTTP)
    normalization.py   URL / company / title / location normalisation, dedupe key
    cache.py           DB-level API cache
    ingestion.py       idempotent upsert, duplicate linking, stale deactivation
    filtering.py       cheap pre-filters (SQL + pure-Python twin)
    summarizer.py      JobSummary + embedding (cached)
    ranking.py         pgvector cosine shortlist
    analysis.py        LLM match analysis (cached)
    tailoring.py       tailored resume generation
    verification.py    fabrication checks
    pipeline.py        end-to-end orchestration
alembic/               migrations (0001 creates schema + HNSW index)
tests/                 unit tests (no DB / no API keys needed)
```

## Tests

```bash
make test
```

## Roadmap

Jooble source · discovered-company auto-registration into `companies` · semantic near-duplicate detection ·
Redis/Celery when ingestion needs to run in the background · UI.
# job-applying-automation
