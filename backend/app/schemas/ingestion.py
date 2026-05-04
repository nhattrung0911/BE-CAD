from pydantic import BaseModel


class DrawingIngestRequest(BaseModel):
    product_id: str
    content: str


class DrawingIngestResponse(BaseModel):
    product_id: str
    dimensions: dict
    metadata: dict
    raw_sha256: str
