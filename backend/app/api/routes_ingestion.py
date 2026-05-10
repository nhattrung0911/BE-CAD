import re

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.core.auth import ROLE_UPLOADER, AuthPrincipal, client_ip, require_role
from app.core.config import settings
from app.core.database import get_db
from app.core.rate_limit import rate_limit

_ingest_rate_limit = rate_limit(name="ingest_2d", limit=30, window_seconds=60.0)
from app.ingestion.svg_parser import parse_spec_table_text, parse_svg_dimension_labels
from app.repositories.parsed_drawings import ParsedDrawingRepository
from app.schemas.ingestion import DrawingIngestRequest, DrawingIngestResponse
from app.services.audit_service import record_audit
from app.services.hash_service import sha256_bytes

router = APIRouter(prefix="/ingest", tags=["ingestion"])

_PRODUCT_ID_RE = re.compile(r"[A-Za-z0-9._-]+")
SUPPORTED_DRAWING_EXTS = {"svg", "txt"}


def _persist_drawing(
    db: Session,
    product_id: str,
    content: str,
    *,
    principal: AuthPrincipal,
    request: Request,
) -> DrawingIngestResponse:
    dimensions = parse_svg_dimension_labels(content)
    metadata = parse_spec_table_text(content)
    raw_sha = sha256_bytes(content.encode("utf-8"))
    ParsedDrawingRepository(db).create(
        product_id=product_id,
        dimensions=dimensions,
        metadata=metadata,
        raw_sha256=raw_sha,
    )
    record_audit(
        db,
        action="ingest.drawing",
        user_id=principal.user_id,
        target_type="parsed_drawing",
        target_id=product_id,
        detail={"raw_sha256": raw_sha, "machine": principal.is_machine},
        ip_address=client_ip(request),
    )
    db.commit()
    return DrawingIngestResponse(
        product_id=product_id, dimensions=dimensions, metadata=metadata, raw_sha256=raw_sha
    )


@router.post("/2d", response_model=DrawingIngestResponse)
def ingest_2d(
    payload: DrawingIngestRequest,
    request: Request,
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_role(ROLE_UPLOADER)),
    __: None = Depends(_ingest_rate_limit),
):
    return _persist_drawing(db, payload.product_id, payload.content, principal=principal, request=request)


@router.post(
    "/2d/upload",
    response_model=DrawingIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_2d_upload(
    request: Request,
    product_id: str = Form(..., min_length=1, max_length=128),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    principal: AuthPrincipal = Depends(require_role(ROLE_UPLOADER)),
    __: None = Depends(_ingest_rate_limit),
):
    """Multipart variant for non-technical operators: drag/drop SVG or text drawing."""
    if not _PRODUCT_ID_RE.fullmatch(product_id):
        raise HTTPException(status_code=400, detail="product_id must match [A-Za-z0-9._-]+")

    suffix = (file.filename or "").rsplit(".", 1)[-1].lower() if file.filename else ""
    if suffix not in SUPPORTED_DRAWING_EXTS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported drawing extension '{suffix}'. Allowed: {sorted(SUPPORTED_DRAWING_EXTS)}",
        )

    raw = await file.read()
    if len(raw) > settings.max_upload_bytes:
        raise HTTPException(status_code=413, detail="Uploaded drawing exceeds MAX_UPLOAD_BYTES")
    try:
        content = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Drawing must be UTF-8 text (SVG/TXT)")
    if len(content) > settings.max_drawing_content_chars:
        raise HTTPException(
            status_code=413,
            detail="Drawing content exceeds MAX_DRAWING_CONTENT_CHARS",
        )
    return _persist_drawing(db, product_id, content, principal=principal, request=request)
