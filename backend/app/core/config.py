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
    admin_api_key: str | None = None
    admin_api_key_header: str = "X-Admin-API-Key"
    auto_create_schema: bool = True
    require_redis_for_ready: bool = False


settings = Settings()
