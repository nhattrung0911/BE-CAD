import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.core.database import init_db, should_auto_create_schema
from app.api.routes_auth import router as auth_router
from app.api.routes_geometry import router as geometry_router
from app.api.routes_ingestion import router as ingestion_router
from app.api.routes_model_jobs import router as model_jobs_router
from app.api.routes_metrics import router as metrics_router
from app.api.routes_products import router as products_router
from app.api.routes_models import router as models_router
from app.api.routes_raw_assets import router as raw_assets_router
from app.api.routes_vendor_assets import router as vendor_assets_router
from app.services.health_service import readiness_payload
from app.services.observability import record_request, reset_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("fastener_cad")

app = FastAPI(title=settings.app_name)
app.state.metrics = reset_metrics()

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=[settings.request_id_header],
)

if should_auto_create_schema():
    init_db()
settings.artifact_base_dir.mkdir(parents=True, exist_ok=True)
settings.raw_asset_base_dir.mkdir(parents=True, exist_ok=True)
# Generated artifacts are public-by-design (we sign their content addresses with
# stable hashes), so mount as static. Raw vendor assets are license-gated and
# served via the dedicated router (raw_assets_router) — never as bare static files.
app.mount(settings.public_artifact_prefix, StaticFiles(directory=str(settings.artifact_base_dir)), name="artifacts")

app.include_router(auth_router, prefix="/api/v1")
app.include_router(products_router, prefix="/api/v1")
app.include_router(models_router, prefix="/api/v1")
app.include_router(geometry_router, prefix="/api/v1")
app.include_router(model_jobs_router, prefix="/api/v1")
app.include_router(vendor_assets_router, prefix="/api/v1")
app.include_router(ingestion_router, prefix="/api/v1")
app.include_router(raw_assets_router)
app.include_router(metrics_router)


@app.middleware("http")
async def request_id_logging(request: Request, call_next):
    request_id = request.headers.get(settings.request_id_header, str(uuid.uuid4()))
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = int((time.perf_counter() - start) * 1000)
    record_request(elapsed_ms=elapsed_ms, metrics=request.app.state.metrics)
    response.headers[settings.request_id_header] = request_id
    logger.info("request_id=%s method=%s path=%s status=%s elapsed_ms=%s", request_id, request.method, request.url.path, response.status_code, elapsed_ms)
    return response


@app.get("/health")
def health():
    return {"status": "ok", "environment": settings.environment, "cad_backend": settings.cad_backend}


@app.get("/ready")
def ready():
    status_code, payload = readiness_payload()
    return JSONResponse(status_code=status_code, content=payload)

