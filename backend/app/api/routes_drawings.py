from fastapi import APIRouter, Depends, HTTPException, Response

from app.core.config import settings
from app.core.rate_limit import rate_limit
from app.services.product_service import product_service
from app.services.projection_service import VIEWS, drawing_svg

router = APIRouter(prefix="/drawings", tags=["drawings"])

_drawing_limit = rate_limit(
    name="public_drawings",
    limit=settings.public_geometry_rate_limit,
    window_seconds=float(settings.public_geometry_rate_window_seconds),
)


@router.get("/{variant_id}/2d.svg")
def variant_drawing_svg(
    variant_id: str,
    view: str = "front",
    _: None = Depends(_drawing_limit),
):
    if view not in VIEWS:
        raise HTTPException(status_code=400, detail=f"Unknown view '{view}'. Allowed: {sorted(VIEWS)}")
    try:
        variant = product_service.get_variant(variant_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Variant not found")

    from app.cad.backends import get_cad_backend

    backend = get_cad_backend("cadquery")
    if not hasattr(backend, "build_shape"):
        raise HTTPException(status_code=503, detail="2D drawing requires the cadquery backend")
    try:
        _, shape = backend.build_shape(variant.product_id, dict(variant.params))
        svg = drawing_svg(shape.val().wrapped, view)
    except KeyError:
        raise HTTPException(status_code=404, detail="No generator for this product")
    except Exception as exc:  # noqa: BLE001 - surface projection failure as 500
        raise HTTPException(status_code=500, detail=f"Projection failed: {exc}")

    return Response(
        content=svg,
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )
