# CLAUDE.md

Guidance for Claude Code when working in this repository.

## What this project is

An AI-powered job search and resume-tailoring assistant. A candidate uploads a resume, the system
ingests jobs from Adzuna (and Greenhouse/Lever company boards), ranks them against the candidate with
pgvector, analyses the best matches with an LLM, and generates a job-specific resume that is verified
against the original so nothing is fabricated. The user always submits the final application manually.

`project_Detail.txt` is the original specification. Treat it as the source of truth for scope and
sequencing. `README.md` documents the built system, the API, and the pipeline.

## Environment

This is worked on from more than one machine. Nothing here is machine-specific except the paths, but
these facts hold on the current office system and are worth re-checking elsewhere:

- Python 3.12, virtualenv at `.venv/` (created by `make install`). Always use `.venv/bin/python`,
  `.venv/bin/pytest`, `.venv/bin/alembic`, not the system interpreter.
- Docker is installed and the daemon is reachable. Other unrelated containers already run on this
  machine, and **port 5432 may already be taken**. If `docker compose up -d db` fails to bind, start a
  throwaway database on another port instead (see "Running against a real database" below).
- Not a git repository. Do not run `git init` or commit unless asked.
- No API keys are configured by default. Everything below runs without them via the `fake` LLM provider.

## Commands

```bash
make install          # venv + requirements
make db               # docker compose up -d db  (pgvector/pgvector:pg16)
make migrate          # alembic upgrade head
make run              # uvicorn on :8000, /docs for OpenAPI
make test             # pytest
```

Alembic takes global flags **before** the subcommand: `.venv/bin/alembic -q upgrade head`, never
`alembic upgrade head -q` (that errors with "unrecognized arguments").

## Testing

Two layers, and a change should keep both green:

1. **Unit tests** (`tests/`) need no database and no API keys. `tests/conftest.py` forces
   `LLM_PROVIDER=fake` and a small embedding dimension. Run with `make test`.
2. **End-to-end smoke test** (`scripts/smoke_test.py`) needs a real PostgreSQL with pgvector. It stubs
   HTTP at the httpx transport level so the database-level API cache is genuinely exercised, and uses
   the `fake` LLM provider with per-schema handlers. It asserts the whole pipeline: PDF upload, ingest
   idempotency, cache hits, ranking order, salary-filter semantics, analysis, verified tailoring, ATS
   deduplication, and posting deactivation.

### Running against a real database

Port 5432 is often busy on this machine. Use a throwaway container on a free port and clean it up
afterwards:

```bash
docker run -d --name jobassist-smoke-db \
  -e POSTGRES_USER=jobs -e POSTGRES_PASSWORD=jobs -e POSTGRES_DB=jobs \
  -p 127.0.0.1:55432:5432 pgvector/pgvector:pg16

export DATABASE_URL=postgresql+psycopg://jobs:jobs@127.0.0.1:55432/jobs LLM_PROVIDER=fake
.venv/bin/alembic -q upgrade head
.venv/bin/python scripts/smoke_test.py

docker rm -f jobassist-smoke-db
```

To reset state between smoke runs: `.venv/bin/alembic -q downgrade base && .venv/bin/alembic -q upgrade head`.
The smoke test asserts exact insert/update counts, so a dirty database produces confusing failures that
look like logic bugs but are not.

### Testing against live job data

Greenhouse and Lever boards are public and need **no API key**, so real end-to-end extraction can be
verified any time. Adzuna does need credentials and fails cleanly without them (the ingestion run is
recorded with `status=failed` and an explanatory error, which is the intended behaviour).

```bash
# real boards, no keys required
curl -s "https://boards-api.greenhouse.io/v1/boards/gitlab/jobs?content=true" | head -c 300
```

Stubbed fixtures are not enough on their own. The location-deduplication bug described below was
invisible to the fixture data and only appeared against a real board. When changing normalisation,
deduplication, or a parser, run it against a live board before trusting it.

## Architecture rules

These encode decisions from the spec. Breaking them changes the product, so raise it rather than
quietly doing it.

- **Never fabricate resume content.** The tailoring prompt permits only reordering, selecting, and
  rewording. `app/services/verification.py` independently re-checks the output against the original
  profile *and* the raw resume text. New employers, titles, dates, degrees, skills, projects,
  certifications, or numbers are hard errors (`rejected`); weak wording overlap is a `flagged` warning.
  Contact details are copied from the original and never taken from the LLM.
- **Never present an aggregator redirect as a direct employer link.** Adzuna gives `source_url` only.
  `apply_url` is set solely when a source provides a verified employer/ATS link, guarded by
  `apply_url_verified`. `app/api/serializers.py:application_block` is the single place that decides what
  the UI is told.
- **Embed summaries, not descriptions.** Each job gets a structured `JobSummary` from the LLM; that
  compact text is what goes into pgvector. Same on the candidate side via `app/services/text_builders.py`.
- **Cheap before expensive.** Filters narrow the set, embeddings shortlist it, and only the shortlist
  reaches the LLM analysis stage.
- **Cache everything durable in PostgreSQL.** Raw API responses (`api_cache`), job summaries and
  embeddings (columns on `jobs`), and analyses (`job_analyses`). A job must never pay twice for the
  same API or LLM call. Redis and Celery are deliberately deferred; do not introduce them without a
  concrete need.
- **Ingestion is idempotent.** Upsert on `(source, source_job_id)`. Duplicates are linked via
  `duplicate_of_id` using normalised URL or a company/title/location key, preferring the copy with a
  verified apply link as canonical. Jobs that vanish are marked inactive, never deleted.
- **Keep the two filter implementations in sync.** `app/services/filtering.py` has a SQL version
  (`filter_conditions`) and a pure-Python twin (`job_passes_filters`) used by tests. Change both.
- **Jobs without salary stay eligible** unless `require_salary` is set. This is deliberate.
- **LLM access goes through `app/llm/`.** Services depend on the `LLMProvider` interface, never on
  OpenAI or Gemini directly, so providers stay swappable.

## Conventions

- SQLAlchemy 2.0 style with `Mapped[...]` / `mapped_column`. Pydantic v2 throughout.
- All LLM output is structured: define a Pydantic schema and call `complete_structured`, which retries
  once on validation failure. Do not parse free text.
- Prompts live in `app/llm/prompts.py`, not inline in services.
- Business logic belongs in `app/services/`. Routes stay thin: validate, delegate, serialise.
- New job sources subclass `JobSource`, map into `NormalizedJob`, and register in
  `app/services/job_sources/registry.py`. Search-style sources implement `search`; company-board
  sources implement `fetch_board`.

## Gotchas

- `EMBEDDING_DIM` (default 768) sizes the pgvector columns **in the initial migration** and is passed to
  the embedding API. Changing it after the first `alembic upgrade` requires a new migration altering
  those columns. It is not a runtime-only setting.
- Import PyMuPDF as `pymupdf`. The `fitz` alias is deprecated and emits a warning.
- The `fake` LLM provider returns schema defaults unless a handler is registered for that schema. When
  writing a test that needs realistic output, register handlers as `scripts/smoke_test.py` does.
- `app/config.py` uses `lru_cache` on `get_settings`, so environment changes mid-process are not picked
  up. Set environment variables before importing application modules.
- **Locations are not simply "first comma-separated part".** Real boards write locations as
  "Remote, Poland", "Remote, Canada; Remote, US", "Bangalore, India". An early version kept only the
  first part, which collapsed every remote posting to `remote` and merged unrelated roles in different
  countries as duplicates. `normalize_location` now unifies country synonyms (UK/United Kingdom) while
  preserving geography, and treats `;` as a separator between whole locations. Tests in
  `tests/test_normalization.py` lock this in.
- `summarize_and_embed_jobs` deliberately skips jobs linked as duplicates, so a small number of rows
  legitimately keep a NULL `summary_embedding`. Assert on *rankable* jobs (active and not a duplicate),
  not on every row.

## Roadmap

Jooble as an additional source, auto-registering companies discovered through job sources, semantic
near-duplicate detection, Redis/Celery once ingestion needs backgrounding, and a UI. Follow the spec's
incremental approach: get the full pipeline working end to end before adding the next component.
