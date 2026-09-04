"""initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-09-04
"""
from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from app.config import get_settings

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

DIM = get_settings().embedding_dim


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("preferences", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "companies",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("normalized_name", sa.String(255), nullable=False, unique=True),
        sa.Column("ats_type", sa.String(50)),
        sa.Column("ats_slug", sa.String(255)),
        sa.Column("website", sa.String(500)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "resumes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("filename", sa.String(255)),
        sa.Column("raw_text", sa.Text, nullable=False),
        sa.Column("profile", postgresql.JSONB),
        sa.Column("profile_text", sa.Text),
        sa.Column("profile_embedding", Vector(DIM)),
        sa.Column("parser_model", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "jobs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("source_job_id", sa.String(255), nullable=False),
        sa.Column("company_id", sa.Integer, sa.ForeignKey("companies.id", ondelete="SET NULL")),
        sa.Column("company_name", sa.String(255)),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("location", sa.String(255)),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("salary_min", sa.Float),
        sa.Column("salary_max", sa.Float),
        sa.Column("salary_currency", sa.String(10)),
        sa.Column("remote", sa.Boolean),
        sa.Column("employment_type", sa.String(50)),
        sa.Column("posted_at", sa.DateTime(timezone=True)),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("last_verified_at", sa.DateTime(timezone=True)),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("source_url", sa.String(2000)),
        sa.Column("normalized_url", sa.String(2000)),
        sa.Column("apply_url", sa.String(2000)),
        sa.Column("apply_url_verified", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("dedupe_key", sa.String(800)),
        sa.Column("duplicate_of_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="SET NULL")),
        sa.Column("summary", postgresql.JSONB),
        sa.Column("summary_text", sa.Text),
        sa.Column("summary_embedding", Vector(DIM)),
        sa.Column("summary_model", sa.String(100)),
        sa.Column("raw", postgresql.JSONB),
        sa.UniqueConstraint("source", "source_job_id", name="uq_jobs_source_source_job_id"),
    )
    op.create_index("ix_jobs_dedupe_key", "jobs", ["dedupe_key"])
    op.create_index("ix_jobs_normalized_url", "jobs", ["normalized_url"])
    op.create_index("ix_jobs_active_posted", "jobs", ["is_active", "posted_at"])
    # HNSW index for cosine similarity on the job summary embeddings
    op.execute(
        "CREATE INDEX ix_jobs_summary_embedding_hnsw ON jobs "
        "USING hnsw (summary_embedding vector_cosine_ops)"
    )

    op.create_table(
        "job_analyses",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("resume_id", sa.Integer, sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("match_score", sa.Float, nullable=False),
        sa.Column("matched_skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("missing_skills", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("experience_compatibility", sa.String(50)),
        sa.Column("location_compatibility", sa.String(50)),
        sa.Column("explanation", sa.Text),
        sa.Column("result", postgresql.JSONB, nullable=False),
        sa.Column("model", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("resume_id", "job_id", name="uq_job_analyses_resume_job"),
    )

    op.create_table(
        "tailored_resumes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("resume_id", sa.Integer, sa.ForeignKey("resumes.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("job_id", sa.Integer, sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("content", postgresql.JSONB, nullable=False),
        sa.Column("markdown", sa.Text, nullable=False),
        sa.Column("verification_status", sa.String(20), nullable=False),
        sa.Column("verification_issues", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("model", sa.String(100)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("params", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("fetched", sa.Integer, nullable=False, server_default="0"),
        sa.Column("inserted", sa.Integer, nullable=False, server_default="0"),
        sa.Column("updated", sa.Integer, nullable=False, server_default="0"),
        sa.Column("duplicates", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.Text),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "api_cache",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("cache_key", sa.String(128), nullable=False, unique=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
    )


def downgrade() -> None:
    for t in ["api_cache", "ingestion_runs", "tailored_resumes", "job_analyses", "jobs", "resumes", "companies", "users"]:
        op.drop_table(t)
