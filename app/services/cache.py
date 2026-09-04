"""Database-level cache for raw external API responses."""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ApiCache


def make_cache_key(source: str, params: dict) -> str:
    payload = json.dumps({"source": source, "params": params}, sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


class ApiCacheService:
    def __init__(self, db: Session, ttl_hours: int = 6):
        self.db = db
        self.ttl = timedelta(hours=ttl_hours)

    def get(self, source: str, params: dict) -> dict | None:
        key = make_cache_key(source, params)
        row = self.db.scalar(select(ApiCache).where(ApiCache.cache_key == key))
        if row is None:
            return None
        if row.expires_at < datetime.now(UTC):
            return None
        return row.payload

    def set(self, source: str, params: dict, payload: dict) -> None:
        key = make_cache_key(source, params)
        now = datetime.now(UTC)
        row = self.db.scalar(select(ApiCache).where(ApiCache.cache_key == key))
        if row is None:
            row = ApiCache(cache_key=key, source=source, payload=payload, fetched_at=now, expires_at=now + self.ttl)
            self.db.add(row)
        else:
            row.payload = payload
            row.fetched_at = now
            row.expires_at = now + self.ttl
        self.db.commit()
