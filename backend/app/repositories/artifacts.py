from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Artifact


class ArtifactRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def create(
        self,
        *,
        product_id: str,
        artifact_type: str,
        format: str,
        quality: str,
        storage_key: str,
        sha256: str,
        file_size: int,
        source: str,
        params_hash: str | None = None,
        metadata: dict | None = None,
    ) -> Artifact:
        artifact = Artifact(
            product_id=product_id,
            artifact_type=artifact_type,
            format=format,
            quality=quality,
            storage_key=storage_key,
            sha256=sha256,
            file_size=file_size,
            source=source,
            params_hash=params_hash,
            metadata_json=metadata,
        )
        self.session.add(artifact)
        self.session.flush()
        return artifact

    def find_by_storage_key(self, storage_key: str) -> Artifact | None:
        return self.session.scalar(select(Artifact).where(Artifact.storage_key == storage_key))

    def find_by_id(self, artifact_id: int) -> Artifact | None:
        return self.session.get(Artifact, artifact_id)

    def find_resolved_model(self, product_id: str, params_hash: str, fmt: str, quality: str) -> Artifact | None:
        return self.session.scalar(
            select(Artifact).where(
                Artifact.product_id == product_id,
                Artifact.params_hash == params_hash,
                Artifact.format == fmt,
                Artifact.quality == quality,
            )
        )

    def find_by_params_hash(self, params_hash: str, fmt: str | None = None, quality: str | None = None) -> Artifact | None:
        stmt = select(Artifact).where(Artifact.params_hash == params_hash)
        if fmt is not None:
            stmt = stmt.where(Artifact.format == fmt)
        if quality is not None:
            stmt = stmt.where(Artifact.quality == quality)
        return self.session.scalar(stmt)

    def update_blob_metadata(
        self,
        artifact: Artifact,
        *,
        storage_key: str,
        sha256: str,
        file_size: int,
        metadata: dict | None = None,
    ) -> Artifact:
        artifact.storage_key = storage_key
        artifact.sha256 = sha256
        artifact.file_size = file_size
        if metadata is not None:
            artifact.metadata_json = metadata
        self.session.flush()
        return artifact
