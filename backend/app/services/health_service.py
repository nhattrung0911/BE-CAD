import logging
from sqlalchemy import text

logger = logging.getLogger(__name__)

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.cache_service import cache
from app.services.product_service import product_service
from app.services.storage import make_artifact_storage, make_raw_asset_storage


def readiness_payload() -> tuple[int, dict]:
    checks = {
        "database": _check_database(),
        "artifact_storage": _check_storage(make_artifact_storage),
        "raw_asset_storage": _check_storage(make_raw_asset_storage),
        "catalog": _check_catalog(),
    }
    if settings.require_redis_for_ready:
        checks["redis"] = _check_redis()
    status = "ready" if all(value == "ok" for value in checks.values()) else "not_ready"
    return (200 if status == "ready" else 503), {"status": status, "checks": checks}


def _check_database() -> str:
    try:
        with SessionLocal() as session:
            session.execute(text("SELECT 1"))
        return "ok"
    except Exception as exc:
        logger.warning("Database readiness check failed: %s", exc)
        return "error"


def _check_storage(factory) -> str:
    try:
        storage = factory()
        storage.exists("__readiness_probe__")
        return "ok"
    except Exception as exc:
        logger.warning("Storage readiness check failed: %s", exc)
        return "error"


def _check_redis() -> str:
    if not settings.redis_url:
        return "missing"
    return "ok" if cache.is_connected() else "error"


def _check_catalog() -> str:
    snapshot = product_service.catalog_status()
    if settings.environment == "production":
        return "ok" if snapshot.has_persistent_catalog else "empty"
    return "ok" if snapshot.has_persistent_catalog or (snapshot.demo_fallback_allowed and snapshot.demo_catalog_available) else "empty"
