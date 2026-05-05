from pathlib import Path
from app.core.config import settings
from app.core.database import SessionLocal
from app.repositories.artifacts import ArtifactRepository
from app.services.storage import ObjectStorage, make_artifact_storage


class ArtifactService:
    def __init__(self, base_dir: Path | None = None, storage: ObjectStorage | None = None) -> None:
        self.storage = storage or make_artifact_storage()
        self.base_dir = base_dir or settings.artifact_base_dir

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> dict:
        return self.storage.put_bytes(key, data, content_type=content_type)

    def put_generated_model(
        self,
        *,
        product_id: str,
        params_hash: str,
        fmt: str,
        quality: str,
        key: str,
        data: bytes,
        source: str,
        metadata: dict | None = None,
        overwrite_existing: bool = False,
    ) -> dict:
        with SessionLocal() as session:
            repo = ArtifactRepository(session)
            existing = repo.find_resolved_model(product_id, params_hash, fmt, quality)
            if existing:
                if self.exists(existing.storage_key) and not overwrite_existing:
                    session.commit()
                    return {
                        "storage_key": existing.storage_key,
                        "url": f"{settings.public_artifact_prefix}/{existing.storage_key}",
                        "sha256": existing.sha256,
                        "file_size": existing.file_size,
                        "artifact_id": existing.id,
                    }

                target_key = existing.storage_key if overwrite_existing else existing.storage_key
                stored = self.put_bytes(target_key, data)
                repo.update_blob_metadata(
                    existing,
                    storage_key=stored["storage_key"],
                    sha256=stored["sha256"],
                    file_size=stored["file_size"],
                    metadata=metadata,
                )
                session.commit()
                return {**stored, "artifact_id": existing.id}

            stored = self.put_bytes(key, data)
            artifact = repo.create(
                product_id=product_id,
                artifact_type="model",
                format=fmt,
                quality=quality,
                storage_key=stored["storage_key"],
                sha256=stored["sha256"],
                file_size=stored["file_size"],
                source=source,
                params_hash=params_hash,
                metadata=metadata,
            )
            session.commit()
            stored["artifact_id"] = artifact.id
            return stored

    def exists(self, key: str) -> bool:
        return self.storage.exists(key)

    def read_bytes(self, key: str) -> bytes:
        return self.storage.read_bytes(key)


artifact_service = ArtifactService()
