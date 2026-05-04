from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict, model_validator


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", protected_namespaces=("settings_",))

    app_name: str = "Fastener CAD Platform"
    environment: str = "local"
    database_url: str = "sqlite:///./storage/app.db"
    artifact_base_dir: Path = Path("storage/artifacts")
    raw_asset_base_dir: Path = Path("storage/raw-assets")
    public_artifact_prefix: str = "/artifacts"
    public_raw_asset_prefix: str = "/raw-assets"
    storage_backend: str = "local"
    s3_bucket: str | None = None
    s3_public_base_url: str | None = None
    redis_url: str | None = None
    cad_backend: str = "mock"
    template_version: str = "cadquery-glb-v1"
    model_sync_generation: bool = True
    request_id_header: str = "X-Request-ID"
    cors_allow_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    admin_api_key: str | None = None
    admin_api_key_header: str = "X-Admin-API-Key"
    auto_create_schema: bool = True
    require_redis_for_ready: bool = False
    max_upload_bytes: int = 100 * 1024 * 1024
    model_cache_ttl_seconds: int = 86400

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]

    @model_validator(mode="after")
    def validate_production_settings(self) -> "Settings":
        if self.environment == "production":
            if self.cad_backend == "mock":
                raise ValueError("CAD_BACKEND=mock is not allowed in production. Set CAD_BACKEND=cadquery")
            if self.auto_create_schema:
                raise ValueError("AUTO_CREATE_SCHEMA=true is not allowed in production. Use Alembic migrations.")
            if not self.require_redis_for_ready:
                raise ValueError(
                    "REQUIRE_REDIS_FOR_READY must be true in production to prevent split-brain cache."
                )
        return self


settings = Settings()
