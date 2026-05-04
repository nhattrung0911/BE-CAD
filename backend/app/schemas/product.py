from typing import Any
from pydantic import BaseModel


class ParameterSpec(BaseModel):
    name: str
    label: str
    type: str = "number"
    unit: str = "mm"
    required: bool = True
    values: list[Any] | None = None


class Product(BaseModel):
    product_id: str
    standard: str
    family: str
    name: str
    unit: str = "mm"
    parameters: list[ParameterSpec]


class ProductVariant(BaseModel):
    variant_id: str
    product_id: str
    sku: str
    label: str
    diameter_label: str
    params: dict[str, Any]
    material: str = "steel"
    standard: str
    geometry: dict[str, str]
