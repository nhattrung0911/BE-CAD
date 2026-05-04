from typing import Any, Literal

from pydantic import BaseModel, Field

from app.schemas.model import ArtifactResponse


GeometryLod = Literal["low", "medium", "high"]


class GeometryGenerateRequest(BaseModel):
    product_id: str
    params: dict[str, Any] = Field(default_factory=dict)
    lod: GeometryLod = "medium"
    format: Literal["glb"] = "glb"


class GeometryResponse(BaseModel):
    status: Literal["ready", "queued", "failed"]
    hash: str | None = None
    hash_url: str | None = None
    variant_id: str | None = None
    lod: GeometryLod
    product_id: str
    params: dict[str, Any]
    artifact: ArtifactResponse | None = None
    cache: Literal["hit", "miss"] = "miss"
    source: str | None = None
    job_id: str | None = None
    message: str | None = None
