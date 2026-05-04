from sqlalchemy.orm import Session

from app.db.models import ParsedDrawing


class ParsedDrawingRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(self, *, product_id: str, dimensions: dict, metadata: dict, raw_sha256: str) -> ParsedDrawing:
        drawing = ParsedDrawing(
            product_id=product_id,
            dimensions_json=dimensions,
            metadata_json=metadata,
            raw_sha256=raw_sha256,
        )
        self.session.add(drawing)
        self.session.flush()
        return drawing
