from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.ingestion.svg_parser import parse_spec_table_text, parse_svg_dimension_labels
from app.repositories.parsed_drawings import ParsedDrawingRepository
from app.schemas.ingestion import DrawingIngestRequest, DrawingIngestResponse
from app.services.hash_service import sha256_bytes

router = APIRouter(prefix="/ingest", tags=["ingestion"])


@router.post("/2d", response_model=DrawingIngestResponse)
def ingest_2d(request: DrawingIngestRequest, db: Session = Depends(get_db)):
    dimensions = parse_svg_dimension_labels(request.content)
    metadata = parse_spec_table_text(request.content)
    raw_sha = sha256_bytes(request.content.encode("utf-8"))
    ParsedDrawingRepository(db).create(
        product_id=request.product_id,
        dimensions=dimensions,
        metadata=metadata,
        raw_sha256=raw_sha,
    )
    db.commit()
    return DrawingIngestResponse(product_id=request.product_id, dimensions=dimensions, metadata=metadata, raw_sha256=raw_sha)
