from typing import Literal

from pydantic import BaseModel

from app.schemas.model import ArtifactResponse, ModelFormat, ModelQuality


ModelJobStatus = Literal["pending", "running", "done", "failed"]


class ModelJobResponse(BaseModel):
    job_id: str
    queue_name: str
    status: ModelJobStatus
    product_id: str
    format: ModelFormat
    quality: ModelQuality
    artifact: ArtifactResponse | None = None
    error_message: str | None = None
