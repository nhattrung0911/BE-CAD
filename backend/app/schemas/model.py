from typing import Any, Literal
from pydantic import BaseModel, Field


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


class ModelResolveResponse(BaseModel):
    status: Literal["ready", "queued", "failed"]
    artifact: ArtifactResponse | None = None
    cache: Literal["hit", "miss"] = "miss"
    source: str | None = None
    job_id: str | None = None
    message: str | None = None
