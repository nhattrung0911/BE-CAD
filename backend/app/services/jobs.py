from dataclasses import dataclass

from app.core.database import SessionLocal
from app.repositories.jobs import JobRepository
from app.services.hash_service import stable_params_hash

QUEUE_PREVIEW_FAST = "preview_fast"
QUEUE_CAD_GENERATE = "cad_generate"
QUEUE_ENGINEERING_STEP = "engineering_step"
QUEUE_BATCH_PREGENERATE = "batch_pregenerate"
QUEUE_NAMES = {QUEUE_PREVIEW_FAST, QUEUE_CAD_GENERATE, QUEUE_ENGINEERING_STEP, QUEUE_BATCH_PREGENERATE}


@dataclass
class QueuedJob:
    job_id: str
    queue_name: str
    status: str
    product_id: str
    format: str
    quality: str
    artifact_id: int | None = None
    error_message: str | None = None


def queue_for_request(fmt: str, quality: str) -> str:
    if quality == "preview" and fmt == "glb":
        return QUEUE_PREVIEW_FAST
    if fmt == "step":
        return QUEUE_ENGINEERING_STEP
    return QUEUE_CAD_GENERATE


def enqueue_generation_job(
    *,
    queue_name: str,
    product_id: str,
    params: dict,
    fmt: str,
    quality: str,
    template_version: str = "v0",
) -> QueuedJob:
    if queue_name not in QUEUE_NAMES:
        raise ValueError(f"Unknown queue: {queue_name}")
    params_hash = stable_params_hash(product_id, template_version, quality, fmt, params)
    job_id = f"job_{queue_name}_{params_hash}"
    with SessionLocal() as session:
        repo = JobRepository(session)
        existing = repo.find_by_job_id(job_id)
        if existing:
            if existing.status == "failed":
                repo.mark_pending(existing)
                session.commit()
            return QueuedJob(
                job_id=existing.job_id,
                queue_name=existing.queue_name,
                status=existing.status,
                product_id=existing.product_id,
                format=existing.format,
                quality=existing.quality,
                artifact_id=existing.result_artifact_id,
                error_message=existing.error_message,
            )
        job = repo.create(
            job_id=job_id,
            queue_name=queue_name,
            product_id=product_id,
            params=params,
            params_hash=params_hash,
            fmt=fmt,
            quality=quality,
        )
        session.commit()
        return QueuedJob(
            job_id=job.job_id,
            queue_name=job.queue_name,
            status=job.status,
            product_id=job.product_id,
            format=job.format,
            quality=job.quality,
            artifact_id=job.result_artifact_id,
            error_message=job.error_message,
        )
