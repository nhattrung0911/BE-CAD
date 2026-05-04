from fastapi import APIRouter, HTTPException
from app.services.product_service import product_service

router = APIRouter(prefix="/products", tags=["products"])


@router.get("")
def list_products():
    return product_service.list_products()


@router.get("/{product_id}")
def get_product(product_id: str):
    try:
        return product_service.get_product(product_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Product not found")


@router.get("/{product_id}/parameters")
def get_parameters(product_id: str):
    try:
        return product_service.get_product(product_id).parameters
    except KeyError:
        raise HTTPException(status_code=404, detail="Product not found")


@router.get("/{product_id}/variants")
def list_variants(product_id: str):
    try:
        return product_service.grouped_variants(product_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Product not found")
