from fastapi import APIRouter, HTTPException, Request, Response

from app.core.config import settings
from app.core.database import SessionLocal
from app.domain.geometry_hashes import params_for_lod
from app.repositories.artifacts import ArtifactRepository
from app.schemas.geometry import GeometryGenerateRequest, GeometryLod, GeometryResponse
from app.schemas.model import ModelResolveRequest
from app.services.artifact_service import artifact_service
from app.services.hash_service import stable_params_hash
from app.services.model_resolver import model_resolver
from app.services.product_service import product_service
from app.workers.tasks import AsyncDispatchUnavailable

router = APIRouter(prefix="/geometry", tags=["geometry"])


def _resolve_geometry(
    *,
    http_request: Request,
    product_id: str,
    params: dict,
    lod: GeometryLod,
    variant_id: str | None = None,
) -> GeometryResponse:
    try:
        product_service.validate_params(product_id, params)
    except KeyError:
        raise HTTPException(status_code=404, detail="Product not found")
    except ValueError as exc:
        detail = exc.args[0] if exc.args else "Invalid product parameters"
        raise HTTPException(status_code=400, detail=detail)

    resolver_params = params_for_lod(params, lod)
    params_hash = stable_params_hash(product_id, settings.template_version, "preview", "glb", resolver_params)
    try:
        resolved = model_resolver.resolve(
            ModelResolveRequest(
                product_id=product_id,
                params=resolver_params,
                format="glb",
                quality="preview",
            )
        )
    except AsyncDispatchUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    _record_cache_metrics(http_request, resolved.cache)
    if resolved.status == "queued":
        http_request.app.state.metrics["cad_platform_jobs_queued_total"] += 1
    return GeometryResponse(
        status=resolved.status,
        hash=params_hash,
        hash_url=f"/api/v1/geometry/hash/{params_hash}",
        variant_id=variant_id,
        lod=lod,
        product_id=product_id,
        params=params,
        artifact=resolved.artifact,
        cache=resolved.cache,
        source=resolved.source,
        job_id=resolved.job_id,
        message=resolved.message,
    )


@router.post("/generate", response_model=GeometryResponse)
def generate_geometry(request: GeometryGenerateRequest, http_request: Request):
    return _resolve_geometry(http_request=http_request, product_id=request.product_id, params=request.params, lod=request.lod)


@router.get("/variant/{variant_id}", response_model=GeometryResponse)
def geometry_for_variant(variant_id: str, http_request: Request, lod: GeometryLod = "medium"):
    try:
        variant = product_service.get_variant(variant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Variant not found")
    return _resolve_geometry(
        http_request=http_request,
        product_id=variant.product_id,
        params=variant.params,
        lod=lod,
        variant_id=variant.variant_id,
    )


@router.get("/hash/{params_hash}")
def geometry_by_hash(params_hash: str):
    with SessionLocal() as session:
        artifact = ArtifactRepository(session).find_by_params_hash(params_hash, fmt="glb", quality="preview")
        if artifact is None:
            raise HTTPException(status_code=404, detail="Geometry not found")
        data = artifact_service.read_bytes(artifact.storage_key)
    return Response(
        content=data,
        media_type="model/gltf-binary",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
            "ETag": f'"{params_hash}"',
        },
    )


def _record_cache_metrics(http_request: Request, cache_status: str) -> None:
    key = "cad_platform_cache_hits_total" if cache_status == "hit" else "cad_platform_cache_misses_total"
    http_request.app.state.metrics[key] += 1
