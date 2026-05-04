from datetime import UTC, datetime

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.db.models import GeometryCacheMetrics


class GeometryCacheMetricsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def upsert(
        self,
        *,
        params_hash: str,
        product_id: str,
        lod: str,
        file_size_bytes: int | None = None,
        generation_ms: int | None = None,
    ) -> GeometryCacheMetrics:
        self.session.flush()
        existing = self.session.get(GeometryCacheMetrics, params_hash)
        now = datetime.now(UTC)
        if existing is not None:
            existing.access_count += 1
            existing.last_accessed = now
            if file_size_bytes is not None:
                existing.file_size_bytes = file_size_bytes
            if generation_ms is not None:
                existing.generation_ms = generation_ms
            return existing

        metric = GeometryCacheMetrics(
            params_hash=params_hash,
            product_id=product_id,
            lod=lod,
            file_size_bytes=file_size_bytes,
            generation_ms=generation_ms,
            last_accessed=now,
            created_at=now,
        )
        self.session.add(metric)
        return metric

    def top_skus(self, limit: int = 50) -> list[GeometryCacheMetrics]:
        stmt = (
            select(GeometryCacheMetrics)
            .order_by(desc(GeometryCacheMetrics.access_count), desc(GeometryCacheMetrics.last_accessed))
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars())
