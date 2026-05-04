from pydantic import BaseModel, Field, field_validator

from app.core.config import settings


class DrawingIngestRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=128)
    content: str

    @field_validator("content")
    @classmethod
    def _cap_content(cls, value: str) -> str:
        if len(value) > settings.max_drawing_content_chars:
            raise ValueError(
                f"content exceeds MAX_DRAWING_CONTENT_CHARS={settings.max_drawing_content_chars}"
            )
        return value

    @field_validator("product_id")
    @classmethod
    def _safe_product_id(cls, value: str) -> str:
        import re
        if not re.fullmatch(r"[A-Za-z0-9._-]+", value):
            raise ValueError("product_id must match [A-Za-z0-9._-]+")
        return value


class DrawingIngestResponse(BaseModel):
    product_id: str
    dimensions: dict
    metadata: dict
    raw_sha256: str
