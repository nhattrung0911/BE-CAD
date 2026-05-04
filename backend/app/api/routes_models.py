from fastapi import APIRouter, HTTPException
from app.schemas.model import ModelResolveRequest, ModelResolveResponse
from app.services.model_resolver import model_resolver
from app.services.product_service import product_service

router = APIRouter(prefix="/models", tags=["models"])


@router.post("/resolve", response_model=ModelResolveResponse)
def resolve_model(request: ModelResolveRequest):
    try:
        product_service.validate_params(request.product_id, request.params)
    except KeyError:
        raise HTTPException(status_code=404, detail="Product not found")
    except ValueError as exc:
        detail = exc.args[0] if exc.args else "Invalid product parameters"
        raise HTTPException(status_code=400, detail=detail)
    return model_resolver.resolve(request)
