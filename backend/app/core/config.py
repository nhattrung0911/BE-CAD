from pathlib import Path
from pydantic_settings import BaseSettings
from pydantic import ConfigDict


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

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_allow_origins.split(",") if origin.strip()]


settings = Settings()
