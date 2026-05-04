# Fastener CAD Platform - Final Backend

Production-oriented backend foundation for a hybrid fastener CAD pipeline. This folder is the canonical final baseline created from the strongest parts of `fastener-cad-platform` and `demo claude`.

1. Prefer exact vendor 3D assets when available.
2. Fall back to parametric CAD templates.
3. Use 2D SVG/PDF/DXF drawings mainly for metadata extraction and validation.
4. Serve lightweight GLB for the web, STEP/STL for engineering downloads.
5. Keep FE as a thin demo; future FE can replace it using the same API contract.

This repository is intentionally structured for Codex or any dev agent to extend file by file with low ambiguity.

## Quick start

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then test:

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/products/hex-bolt-iso4014/variants
curl http://localhost:8000/api/v1/geometry/variant/hex-bolt-iso4014-m8x30?lod=medium
curl -X POST http://localhost:8000/api/v1/models/resolve \
  -H 'Content-Type: application/json' \
  -d '{"product_id":"hex-bolt-iso4014","params":{"d":6,"L":30,"P":1,"k":4,"s":10,"b":18},"format":"glb","quality":"preview"}'
```

The default local backend uses a deterministic mock CAD exporter so fast unit tests can run without heavy OCC startup. Set `CAD_BACKEND=cadquery` to enable real CadQuery/OCC generation. In production, preview GLB is exported through CadQuery `Assembly.export("*.glb")`; STEP/STL still use CadQuery exporters.

## Repo map

```text
backend/              FastAPI app, resolver, mock CAD templates, tests
frontend-demo/        Minimal FE demo for future FE team contract validation
docs/                 Architecture, API, roadmap, Codex prompts, CTO tasks
infra/                Docker, docker-compose, Nginx notes, env examples
```

## Important architectural decision

Do not scale one mesh to create all sizes. Exact vendor model is allowed only when size and parameters match. Otherwise use parametric templates and dimension tables.

The frontend flow is:

```text
Customer selects product
        |
Customer selects variant size
        |
GET /api/v1/products/{product_id}/variants
        |
GET /api/v1/geometry/variant/{variant_id}?lod=medium
        |
Three.js loads the returned GLB artifact or immutable hash URL
        |
Viewer auto-fits camera to the model bounding box; it must not resize a model to fake another SKU
```

## Backend capabilities

- SQLAlchemy models and repositories for artifacts, vendor assets, parsed drawings, and generation jobs.
- Alembic migration in `backend/alembic/versions/20260429_0001_initial_platform_tables.py`.
- DB-backed artifact lookup before generation, local storage by default, and an S3-ready storage interface.
- Redis-backed cache/locks when `REDIS_URL` is configured, with in-memory fallback for tests and local runs.
- Named async job queues: `preview_fast`, `cad_generate`, `engineering_step`, and `batch_pregenerate`.
- Real worker task bodies update model jobs from `pending` to `running`, then `done` or `failed`.
- `GET /api/v1/model-jobs/{job_id}` returns queue state, failure details, and the generated artifact once available.
- Vendor 3D ingestion at `POST /api/v1/vendor-assets` for STEP/STL/GLB with checksum, raw storage, license status, and validation status.
- 2D metadata ingestion at `POST /api/v1/ingest/2d` for dimension labels such as `h:6.8-7.2`, `d1:12.8-13.2`, `OD:99.8-100.2`, plus unit/material/standard/size/name/surface/barcode text.
- Request ID logging, `/health`, real `/ready` dependency checks, and placeholder `/metrics`.
- Frontend contract routes for size pickers and Three.js viewers:
  - `GET /api/v1/products/{product_id}/variants`
  - `GET /api/v1/geometry/variant/{variant_id}?lod=low|medium|high`
  - `POST /api/v1/geometry/generate`
  - `GET /api/v1/geometry/hash/{hash}`

## Resolver order

1. Cached artifact from memory/Redis or DB.
2. Exact registered vendor 3D asset for the requested product and format.
3. Parametric CAD template through the selected backend.
4. Queued async generation for heavy engineering formats.
5. 2D metadata fallback when only drawing data exists.

The default `mock` backend can inline preview GLB generation for backward compatibility. Engineering STEP/STL requests are queued when no cached or vendor asset exists.

With `MODEL_SYNC_GENERATION=false`, uncached resolver requests create a model job and dispatch it to the appropriate Celery queue. Docker Compose runs the API with sync generation disabled and starts a worker subscribed to all model-generation queues.

## Operations

```bash
cd backend
PYTHONPATH=. alembic upgrade head
PYTHONPATH=. pytest -q -p no:cacheprovider
PYTHONPATH=. python scripts/local_smoke.py
PYTHONPATH=. python scripts/pregenerate_top_skus.py --input ../data/top_skus.example.json
```

On Windows PowerShell from `final/backend`:

```powershell
$env:PYTHONDONTWRITEBYTECODE='1'
python -m pytest -q -p no:cacheprovider
python scripts/local_smoke.py
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Docker Compose includes API, worker, Redis, Postgres, and MinIO:

```bash
cd infra
docker compose --env-file .env.example up --build
```

For production-style configuration, use `infra/.env.production.example` as the placeholder template and provide real secrets outside git.
