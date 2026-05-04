import time

from app.core.config import settings
from app.core.database import SessionLocal
from app.cad.backends import get_cad_backend
from app.repositories.artifacts import ArtifactRepository
from app.repositories.vendor_assets import VendorAssetRepository
from app.services.artifact_service import artifact_service
from app.services.cache_service import MODEL_CACHE_TTL, cache
from app.services.hash_service import stable_params_hash
from app.services.jobs import enqueue_generation_job, queue_for_request
from app.services.observability import record_inline_generation
from app.services.job_runner import model_artifact_key
from app.schemas.model import ModelResolveRequest, ModelResolveResponse, ArtifactResponse


class ModelResolver:
    def resolve(self, request: ModelResolveRequest) -> ModelResolveResponse:
        params_hash = stable_params_hash(
            request.product_id,
            settings.template_version,
            request.quality,
            request.format,
            request.params,
        )
        artifact_key = model_artifact_key(request.product_id, params_hash, request.quality, request.format)
        cache_key = f"model:{artifact_key}"

        cached = cache.get(cache_key)
        if cached:
            return ModelResolveResponse(
                status="ready",
                artifact=ArtifactResponse(**cached["artifact"]),
                cache="hit",
                source=cached.get("source", "cache"),
            )

        with SessionLocal() as session:
            artifacts = ArtifactRepository(session)
            existing = artifacts.find_resolved_model(request.product_id, params_hash, request.format, request.quality)
            if existing and artifact_service.exists(existing.storage_key):
                artifact_response = self._artifact_response(
                    fmt=existing.format,
                    quality=existing.quality,
                    url=f"{settings.public_artifact_prefix}/{existing.storage_key}",
                    sha256=existing.sha256,
                    file_size=existing.file_size,
                )
                cache.set(
                    cache_key,
                    {"artifact": artifact_response.model_dump(), "source": "cache_db"},
                    ttl_seconds=MODEL_CACHE_TTL,
                )
                return ModelResolveResponse(status="ready", artifact=artifact_response, cache="hit", source="cache_db")

            vendor_repo = VendorAssetRepository(session)
            # Variant-specific override takes priority over product-level vendor file.
            vendor = None
            vendor_source = None
            if request.variant_id:
                vendor = vendor_repo.find_for_variant(request.variant_id, request.format)
                if vendor:
                    vendor_source = "vendor_variant"
            if vendor is None:
                vendor = vendor_repo.find_exact(request.product_id, request.format)
                if vendor:
                    vendor_source = "vendor_exact"
            if vendor:
                artifact_response = self._artifact_response(
                    fmt=vendor.format,
                    quality=request.quality,
                    url=f"{settings.public_raw_asset_prefix}/{vendor.storage_key}",
                    sha256=vendor.sha256,
                    file_size=vendor.file_size,
                )
                cache.set(
                    cache_key,
                    {"artifact": artifact_response.model_dump(), "source": vendor_source},
                    ttl_seconds=MODEL_CACHE_TTL,
                )
                return ModelResolveResponse(status="ready", artifact=artifact_response, cache="miss", source=vendor_source)

        lock_ttl = (
            settings.inline_lock_ttl_seconds
            if self._may_generate_inline(request)
            else settings.queued_lock_ttl_seconds
        )
        lock = cache.acquire_lock(f"lock:{cache_key}", ttl_seconds=lock_ttl)
        if lock is None:
            from app.workers.tasks import ensure_async_dispatch_available

            ensure_async_dispatch_available()
            job = enqueue_generation_job(
                queue_name=queue_for_request(request.format, request.quality),
                product_id=request.product_id,
                params=request.params,
                fmt=request.format,
                quality=request.quality,
                template_version=settings.template_version,
            )
            return ModelResolveResponse(status="queued", cache="miss", source="queued_parametric", job_id=job.job_id)

        try:
            if not self._may_generate_inline(request):
                from app.workers.tasks import dispatch_generation_job, ensure_async_dispatch_available

                ensure_async_dispatch_available()
                job = enqueue_generation_job(
                    queue_name=queue_for_request(request.format, request.quality),
                    product_id=request.product_id,
                    params=request.params,
                    fmt=request.format,
                    quality=request.quality,
                    template_version=settings.template_version,
                )
                dispatch_generation_job(job.queue_name, job.job_id)
                return ModelResolveResponse(status="queued", cache="miss", source="queued_parametric", job_id=job.job_id)

            started_at = time.perf_counter()
            generated = get_cad_backend(settings.cad_backend).generate(request.product_id, request.params, request.format, request.quality)
            artifact = artifact_service.put_generated_model(
                product_id=request.product_id,
                params_hash=params_hash,
                fmt=request.format,
                quality=request.quality,
                key=artifact_key,
                data=generated.content,
                source="generated_parametric",
                metadata=generated.metadata,
            )
            elapsed_ms = int((time.perf_counter() - started_at) * 1000)
            record_inline_generation(elapsed_ms=elapsed_ms)
            artifact_response = {
                "format": request.format,
                "quality": request.quality,
                "url": artifact["url"],
                "sha256": artifact["sha256"],
                "file_size": artifact["file_size"],
            }
            cache.set(
                cache_key,
                {"artifact": artifact_response, "source": "generated_parametric"},
                ttl_seconds=MODEL_CACHE_TTL,
            )
            return ModelResolveResponse(
                status="ready",
                artifact=ArtifactResponse(**artifact_response),
                cache="miss",
                source="generated_parametric",
            )
        except Exception as exc:
            from app.workers.tasks import AsyncDispatchUnavailable

            if isinstance(exc, AsyncDispatchUnavailable):
                raise
            return ModelResolveResponse(status="failed", message=str(exc), cache="miss")
        finally:
            cache.release_lock(lock)

    def _may_generate_inline(self, request: ModelResolveRequest) -> bool:
        return (
            settings.model_sync_generation
            and request.format == "glb"
            and request.quality == "preview"
        )

    def _artifact_response(self, *, fmt: str, quality: str, url: str, sha256: str, file_size: int) -> ArtifactResponse:
        return ArtifactResponse(format=fmt, quality=quality, url=url, sha256=sha256, file_size=file_size)


model_resolver = ModelResolver()
