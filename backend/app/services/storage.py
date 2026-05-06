import hashlib
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote

from app.core.config import settings


class ObjectStorage(ABC):
    @abstractmethod
    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> dict:
        raise NotImplementedError

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    def read_bytes(self, key: str) -> bytes:
        raise NotImplementedError


class LocalStorage(ObjectStorage):
    def __init__(self, base_dir: Path, public_prefix: str) -> None:
        self.base_dir = base_dir
        self.public_prefix = public_prefix.rstrip("/")
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> dict:
        path = self._safe_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        sha = hashlib.sha256(data).hexdigest()
        return {
            "storage_key": key,
            "url": f"{self.public_prefix}/{key}",
            "sha256": sha,
            "file_size": len(data),
            "content_type": content_type,
        }

    def exists(self, key: str) -> bool:
        return self._safe_path(key).exists()

    def read_bytes(self, key: str) -> bytes:
        return self._safe_path(key).read_bytes()

    def _safe_path(self, key: str) -> Path:
        if not is_safe_storage_key(key):
            raise ValueError(f"Unsafe storage key: {key}")
        base = self.base_dir.resolve()
        path = (base / key).resolve()
        if path != base and base not in path.parents:
            raise ValueError(f"Unsafe storage key: {key}")
        return path


class S3Storage(ObjectStorage):
    def __init__(self, bucket: str, public_prefix: str) -> None:
        self.bucket = bucket
        self.public_prefix = public_prefix.rstrip("/")
        try:
            import boto3
        except ImportError as exc:
            raise RuntimeError("S3 storage requires boto3 to be installed") from exc
        self.client = boto3.client("s3")

    def put_bytes(self, key: str, data: bytes, content_type: str | None = None) -> dict:
        extra = {"ContentType": content_type} if content_type else None
        kwargs = {"Bucket": self.bucket, "Key": key, "Body": data}
        if extra:
            kwargs["ContentType"] = content_type
        self.client.put_object(**kwargs)
        sha = hashlib.sha256(data).hexdigest()
        return {
            "storage_key": key,
            "url": f"{self.public_prefix}/{key}",
            "sha256": sha,
            "file_size": len(data),
            "content_type": content_type,
        }

    def exists(self, key: str) -> bool:
        try:
            import botocore.exceptions

            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except botocore.exceptions.ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "404":
                return False
            import logging
            logging.getLogger(__name__).warning("S3 head_object failed for key=%s: %s", key, exc)
            raise

    def read_bytes(self, key: str) -> bytes:
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        return obj["Body"].read()


def make_artifact_storage() -> ObjectStorage:
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        return S3Storage(settings.s3_bucket, settings.public_artifact_prefix)
    return LocalStorage(settings.artifact_base_dir, settings.public_artifact_prefix)


def make_raw_asset_storage() -> ObjectStorage:
    if settings.storage_backend == "s3":
        if not settings.s3_bucket:
            raise RuntimeError("S3_BUCKET is required when STORAGE_BACKEND=s3")
        return S3Storage(settings.s3_bucket, settings.public_raw_asset_prefix)
    return LocalStorage(settings.raw_asset_base_dir, settings.public_raw_asset_prefix)


def is_safe_storage_key(key: str) -> bool:
    if not key or key.startswith(("/", "\\")):
        return False
    parts = Path(key).parts
    return all(part not in {"", ".", ".."} for part in parts)


def safe_storage_segment(value: str) -> str:
    cleaned = Path(value).name.strip().replace("\\", "/").split("/")[-1]
    if cleaned in {"", ".", ".."}:
        raise ValueError(f"Unsafe storage segment: {value}")
    return quote(cleaned, safe="")
