from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field


ModelFormat = Literal["glb", "step", "stl"]
ModelQuality = Literal["preview", "engineering"]


class ModelResolveRequest(BaseModel):
    product_id: str
    variant_id: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    format: ModelFormat = "glb"
    quality: ModelQuality = "preview"


class ArtifactResponse(BaseModel):
    format: ModelFormat
    quality: ModelQuality
    url: str
    sha256: str
    file_size: int


class DimensionAnnotationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    label: str
    value_mm: float
    from_point: list[float]
    to_point: list[float]
    axis: str
    color_hex: str
    plane: str


class ModelResolveResponse(BaseModel):
    status: Literal["ready", "queued", "failed"]
    artifact: ArtifactResponse | None = None
    annotations: list[DimensionAnnotationResponse] = Field(default_factory=list)
    cache: Literal["hit", "miss"] = "miss"
    source: str | None = None
    job_id: str | None = None
    message: str | None = None
