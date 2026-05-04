from fastapi import APIRouter, HTTPException, Response

from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories.artifacts import ArtifactRepository
from app.schemas.geometry import GeometryGenerateRequest, GeometryLod, GeometryResponse
from app.schemas.model import ModelResolveRequest
from app.services.artifact_service import artifact_service
from app.services.hash_service import stable_params_hash
from app.services.model_resolver import model_resolver
from app.services.product_service import product_service

router = APIRouter(prefix="/geometry", tags=["geometry"])


def _params_for_lod(params: dict, lod: str) -> dict:
    return {**params, "lod": lod}


def _resolve_geometry(*, product_id: str, params: dict, lod: GeometryLod, variant_id: str | None = None) -> GeometryResponse:
    try:
        product_service.validate_params(product_id, params)
    except KeyError:
        raise HTTPException(status_code=404, detail="Product not found")
    except ValueError as exc:
        detail = exc.args[0] if exc.args else "Invalid product parameters"
        raise HTTPException(status_code=400, detail=detail)

    resolver_params = _params_for_lod(params, lod)
    params_hash = stable_params_hash(product_id, settings.template_version, "preview", "glb", resolver_params)
    resolved = model_resolver.resolve(
        ModelResolveRequest(
            product_id=product_id,
            params=resolver_params,
            format="glb",
            quality="preview",
        )
    )
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
def generate_geometry(request: GeometryGenerateRequest):
    return _resolve_geometry(product_id=request.product_id, params=request.params, lod=request.lod)


@router.get("/variant/{variant_id}", response_model=GeometryResponse)
def geometry_for_variant(variant_id: str, lod: GeometryLod = "medium"):
    try:
        variant = product_service.get_variant(variant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Variant not found")
    return _resolve_geometry(product_id=variant.product_id, params=variant.params, lod=lod, variant_id=variant.variant_id)


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
