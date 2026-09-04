from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.config import get_settings
from app.db.base import Base


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("source", "source_job_id", name="uq_jobs_source_source_job_id"),
        Index("ix_jobs_dedupe_key", "dedupe_key"),
        Index("ix_jobs_normalized_url", "normalized_url"),
        Index("ix_jobs_active_posted", "is_active", "posted_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False)
    source_job_id: Mapped[str] = mapped_column(String(255), nullable=False)

    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id", ondelete="SET NULL"))
    company_name: Mapped[str | None] = mapped_column(String(255))
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[str | None] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    salary_min: Mapped[float | None] = mapped_column(Float)
    salary_max: Mapped[float | None] = mapped_column(Float)
    salary_currency: Mapped[str | None] = mapped_column(String(10))
    remote: Mapped[bool | None] = mapped_column(Boolean)
    employment_type: Mapped[str | None] = mapped_column(String(50))

    # Freshness tracking
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    last_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # URLs: source_url is the aggregator/redirect link; apply_url is only set when verified (employer/ATS)
    source_url: Mapped[str | None] = mapped_column(String(2000))
    normalized_url: Mapped[str | None] = mapped_column(String(2000))
    apply_url: Mapped[str | None] = mapped_column(String(2000))
    apply_url_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Deduplication
    dedupe_key: Mapped[str | None] = mapped_column(String(800))
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id", ondelete="SET NULL"))

    # Structured summary (JobSummary) + embedding; cached so the same job never re-costs an LLM call
    summary: Mapped[dict | None] = mapped_column(JSONB)
    summary_text: Mapped[str | None] = mapped_column(Text)
    summary_embedding = mapped_column(Vector(get_settings().embedding_dim), nullable=True)
    summary_model: Mapped[str | None] = mapped_column(String(100))

    raw: Mapped[dict | None] = mapped_column(JSONB)
