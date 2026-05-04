from fastapi import APIRouter, HTTPException, Request
from app.schemas.model import ModelResolveRequest, ModelResolveResponse
from app.services.model_resolver import model_resolver
from app.services.observability import record_cache_result, record_job_queued
from app.services.product_service import product_service
from app.workers.tasks import AsyncDispatchUnavailable

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/resolve", response_model=ModelResolveResponse)
def resolve_model(request: ModelResolveRequest, http_request: Request):
    try:
        product_service.validate_params(request.product_id, request.params)
    except KeyError:
        raise HTTPException(status_code=404, detail="Product not found")
    except ValueError as exc:
        detail = exc.args[0] if exc.args else "Invalid product parameters"
        raise HTTPException(status_code=400, detail=detail)
    try:
        resolved = model_resolver.resolve(request)
    except AsyncDispatchUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    record_cache_result(cache_status=resolved.cache, metrics=http_request.app.state.metrics)
    if resolved.status == "queued":
        record_job_queued(http_request.app.state.metrics)
    return resolved
