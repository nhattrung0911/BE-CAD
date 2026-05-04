from app.cad.backends import get_cad_backend
from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories.artifacts import ArtifactRepository
from app.repositories.jobs import JobRepository
from app.services.artifact_service import artifact_service
from app.services.cache_service import cache
from app.services.observability import record_job_completed, record_job_failed


def model_artifact_key(product_id: str, params_hash: str, quality: str, fmt: str) -> str:
    return f"{product_id}/{settings.template_version}/{params_hash}/{quality}.{fmt}"


def model_cache_key(product_id: str, params_hash: str, quality: str, fmt: str) -> str:
    return f"model:{model_artifact_key(product_id, params_hash, quality, fmt)}"


def artifact_response_payload(*, fmt: str, quality: str, storage_key: str, sha256: str, file_size: int) -> dict:
    return {
        "format": fmt,
        "quality": quality,
        "url": f"{settings.public_artifact_prefix}/{storage_key}",
        "sha256": sha256,
        "file_size": file_size,
    }


def run_model_generation_job(job_id: str) -> dict:
    with SessionLocal() as session:
        jobs = JobRepository(session)
        job = jobs.find_by_job_id(job_id)
        if job is None:
            raise KeyError(f"Model job not found: {job_id}")
        if job.status == "done":
            return {"job_id": job.job_id, "status": job.status, "artifact_id": job.result_artifact_id}
        jobs.mark_running(job)
        session.commit()

    try:
        generated = get_cad_backend(settings.cad_backend).generate(
            job.product_id,
            job.params_json,
            job.format,
            job.quality,
        )
        key = model_artifact_key(job.product_id, job.params_hash, job.quality, job.format)
        stored = artifact_service.put_generated_model(
            product_id=job.product_id,
            params_hash=job.params_hash,
            fmt=job.format,
            quality=job.quality,
            key=key,
            data=generated.content,
            source="generated_parametric",
            metadata=generated.metadata,
        )
        artifact_id = stored["artifact_id"]
        artifact_payload = {
            "format": job.format,
            "quality": job.quality,
            "url": stored["url"],
            "sha256": stored["sha256"],
            "file_size": stored["file_size"],
        }
        cache.set(
            model_cache_key(job.product_id, job.params_hash, job.quality, job.format),
            {"artifact": artifact_payload, "source": "generated_parametric"},
            ttl_seconds=settings.model_cache_ttl_seconds,
        )
        with SessionLocal() as session:
            jobs = JobRepository(session)
            current = jobs.find_by_job_id(job_id)
            if current is None:
                raise KeyError(f"Model job not found after generation: {job_id}")
            jobs.mark_done(current, artifact_id)
            session.commit()
        record_job_completed()
        return {"job_id": job_id, "status": "done", "artifact_id": artifact_id}
    except Exception as exc:
        with SessionLocal() as session:
            jobs = JobRepository(session)
            current = jobs.find_by_job_id(job_id)
            if current is not None:
                jobs.mark_failed(current, str(exc))
                session.commit()
        record_job_failed()
        return {"job_id": job_id, "status": "failed", "error_message": str(exc)}


def get_model_job_payload(job_id: str) -> dict | None:
    with SessionLocal() as session:
        job = JobRepository(session).find_by_job_id(job_id)
        if job is None:
            return None
        artifact_payload = None
        if job.result_artifact_id:
            artifact = ArtifactRepository(session).find_by_id(job.result_artifact_id)
            if artifact is not None:
                artifact_payload = artifact_response_payload(
                    fmt=artifact.format,
                    quality=artifact.quality,
                    storage_key=artifact.storage_key,
                    sha256=artifact.sha256,
                    file_size=artifact.file_size,
                )
        return {
            "job_id": job.job_id,
            "queue_name": job.queue_name,
            "status": job.status,
            "product_id": job.product_id,
            "format": job.format,
            "quality": job.quality,
            "artifact": artifact_payload,
            "error_message": job.error_message,
        }
